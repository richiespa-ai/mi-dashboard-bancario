import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

st.set_page_config(
    page_title="Dashboard Bancario",
    page_icon="🏦",
    layout="wide"
)

st.title("🏦 Dashboard Bancario y Control de Finanzas")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1tfnhAs8VeaciHXWJ4J0UDxkhvOiuR-_FvDRnHD0tqxI/edit"

@st.cache_data(ttl=60)
def load_all_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    try:
        df_mov = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Movimientos", ttl="1m")
    except Exception:
        df_mov = conn.read(spreadsheet=SPREADSHEET_URL, ttl="1m")

    cols_esperadas = [
        "ID_Movimiento", "Fecha", "Cuenta / Banco", "Concepto / Descripción",
        "Tipo", "Categoría", "Subcategoría", "Importe", "Estado", "Notas / Observaciones"
    ]
    
    if df_mov.empty or not any(col in df_mov.columns for col in ["Importe", "Fecha"]):
        df_mov = pd.DataFrame(columns=cols_esperadas)
    else:
        for col in cols_esperadas:
            if col not in df_mov.columns:
                df_mov[col] = None
        df_mov['Fecha'] = pd.to_datetime(df_mov['Fecha'], errors='coerce')
        df_mov['Importe'] = pd.to_numeric(df_mov['Importe'], errors='coerce').fillna(0.0)

    try:
        df_cat = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Categorías", ttl="1m")
    except Exception:
        df_cat = pd.DataFrame(columns=["Categoría Principal", "Subcategoría", "Tipo"])

    return df_mov, df_cat

try:
    df, df_cat = load_all_data()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# --- SIDEBAR: CARGA DE EXCEL CON ANTIDUPLICADOS ---
st.sidebar.header("📁 Importar Archivo")
uploaded_file = st.sidebar.file_uploader("Subir extracto (Excel o CSV)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    if st.sidebar.button("Volcar a Google Sheets"):
        try:
            if uploaded_file.name.endswith(".csv"):
                df_excel = pd.read_csv(uploaded_file)
            else:
                df_excel = pd.read_excel(uploaded_file)
            
            nuevos_registros = []
            
            # Crear un conjunto (set) con los registros existentes para comparar y evitar duplicados exactos
            # Clave de duplicado: (Fecha en string, Concepto, Importe)
            existentes_set = set()
            if not df.empty:
                for _, r in df.iterrows():
                    f_str = str(r['Fecha'].date()) if pd.notnull(r['Fecha']) else ""
                    c_str = str(r['Concepto / Descripción']).strip().lower()
                    i_val = round(float(r['Importe']), 2)
                    existentes_set.add((f_str, c_str, i_val))
            
            start_id = len(df) + 1
            duplicados_omitidos = 0
            
            for idx, row in df_excel.iterrows():
                fecha_val = row.get("Fecha") or row.get("Fecha Valor") or row.get("F.Operación")
                concepto_val = row.get("Concepto") or row.get("Descripción") or "Movimiento Importado"
                importe_val = row.get("Importe") or row.get("Monto") or 0.0
                
                try:
                    importe_float = float(str(importe_val).replace(".", "").replace(",", ".")) if isinstance(importe_val, str) else float(importe_val)
                    importe_float = round(importe_float, 2)
                except ValueError:
                    importe_float = 0.0
                
                fecha_dt = pd.to_datetime(fecha_val, errors='coerce')
                fecha_str = str(fecha_dt.date()) if pd.notnull(fecha_dt) else str(pd.Timestamp.now().date())
                c_limpio = str(concepto_val).strip().lower()
                
                # Comprobar si ya existe en la base de datos
                firma = (fecha_str, c_limpio, importe_float)
                if firma in existentes_set:
                    duplicados_omitidos += 1
                    continue
                
                # Añadir al set local para evitar duplicados dentro del mismo archivo si los hubiera
                existentes_set.add(firma)
                
                tipo_val = "Ingreso" if importe_float >= 0 else "Gasto"
                
                nuevos_registros.append({
                    "ID_Movimiento": f"MOV-{start_id + len(nuevos_registros):04d}",
                    "Fecha": fecha_str,
                    "Cuenta / Banco": "Banco Importado",
                    "Concepto / Descripción": str(concepto_val),
                    "Tipo": tipo_val,
                    "Categoría": "Sin Categorizar",
                    "Subcategoría": "Pendiente",
                    "Importe": importe_float,
                    "Estado": "Pendiente",
                    "Notas / Observaciones": f"Importado de {uploaded_file.name}"
                })
            
            if nuevos_registros:
                df_nuevos = pd.DataFrame(nuevos_registros)
                
                if df.empty:
                    df_actualizado = df_nuevos
                else:
                    df_copy = df.copy()
                    df_copy['Fecha'] = df_copy['Fecha'].dt.strftime('%Y-%m-%d')
                    df_actualizado = pd.concat([df_copy, df_nuevos], ignore_index=True)
                
                conn = st.connection("gsheets", type=GSheetsConnection)
                conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Movimientos", data=df_actualizado)
                
                st.sidebar.success(f"¡Se añadieron {len(nuevos_registros)} nuevos movimientos! ({duplicados_omitidos} duplicados omitidos).")
                st.cache_data.clear()
                st.rerun()
            else:
                st.sidebar.warning(f"No hay movimientos nuevos para añadir. Todos los registros del archivo ya existían ({duplicados_omitidos} omitidos).")
            
        except Exception as err:
            st.sidebar.error(f"Error: {err}")

# --- MÉTRICAS ---
ingresos = df[df["Importe"] > 0]["Importe"].sum() if not df.empty else 0.0
gastos = df[df["Importe"] < 0]["Importe"].sum() if not df.empty else 0.0
balance = ingresos + gastos

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ingresos Totales", f"{ingresos:,.2f} €")
col2.metric("Gastos Totales", f"{abs(gastos):,.2f} €")
col3.metric("Balance Neto", f"{balance:,.2f} €")
col4.metric("Nº Transacciones", len(df))

st.markdown("---")

# --- TABLA DE DATOS ---
st.subheader("📋 Registro de Movimientos")
if not df.empty:
    df_mostrar = df.copy()
    df_mostrar['Fecha'] = df_mostrar['Fecha'].dt.strftime('%Y-%m-%d')
    st.dataframe(
        df_mostrar.style.format({"Importe": "{:,.2f} €"}),
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("No hay movimientos registrados todavía.")
