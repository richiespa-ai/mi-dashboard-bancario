import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from streamlit_gsheets import GSheetsConnection

st.set_page_config(
    page_title="Dashboard Bancario",
    page_icon="🏦",
    layout="wide"
)

st.title("🏦 Dashboard Bancario y Control de Finanzas")

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1tfnhAs8VeaciHXWJ4J0UDxkhvOiuR-_FvDRnHD0tqxI/edit"
# Pega aquí la URL de tu Google Apps Script (/exec)
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxRDfF6PNIe985d984QHbSP66gBVaD3TJWgEKBvZPzkt9N_PtIa63AN-9dgwrJamV4NCA/exec"

def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_mov = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Movimientos", ttl=0)
    except Exception:
        df_mov = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)

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

    return df_mov

df = load_data()

# --- SIDEBAR: CARGA DE EXCEL ---
st.sidebar.header("📁 Importar Extracto")
uploaded_file = st.sidebar.file_uploader("Subir archivo (Excel o CSV)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    if st.sidebar.button("Volcar a Google Sheets"):
        if APPS_SCRIPT_URL == "TU_URL_DE_GOOGLE_APPS_SCRIPT_AQUI":
            st.sidebar.error("Falta configurar la URL del Apps Script en el código.")
        else:
            try:
                if uploaded_file.name.endswith(".csv"):
                    df_excel = pd.read_csv(uploaded_file)
                else:
                    df_excel = pd.read_excel(uploaded_file)
                
                nuevas_filas = []
                start_id = len(df) + 1
                
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
                    tipo_val = "Ingreso" if importe_float >= 0 else "Gasto"
                    
                    # Estructura de la fila en orden exacto de las columnas del Sheet
                    fila_tabla = [
                        f"MOV-{start_id + len(nuevas_filas):04d}",
                        fecha_str,
                        "Banco Importado",
                        str(concepto_val),
                        tipo_val,
                        "Sin Categorizar",
                        "Pendiente",
                        importe_float,
                        "Pendiente",
                        f"Importado de {uploaded_file.name}"
                    ]
                    nuevas_filas.append(fila_tabla)
                
                if nuevas_filas:
                    # Enviar mediante POST al Apps Script de forma totalmente gratuita y sin GCP
                    response = requests.post(APPS_SCRIPT_URL, json={"rows": nuevas_filas})
                    if response.status_code == 200:
                        st.sidebar.success(f"¡{len(nuevas_filas)} movimientos guardados en Google Sheets!")
                        st.rerun()
                    else:
                        st.sidebar.error(f"Error al sincronizar con Google Sheets: {response.text}")
                else:
                    st.sidebar.warning("No hay filas válidas en el archivo.")
                    
            except Exception as err:
                st.sidebar.error(f"Error procesando el archivo: {err}")

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
    st.warning("Sube un archivo Excel o CSV en el menú lateral para ver los movimientos.")
