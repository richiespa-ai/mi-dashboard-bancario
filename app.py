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

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1tfnhAs8VeaciHXWJ4J0UDxkhvOiuR-_FvDRnHD0tqxI/edit#gid=0"

@st.cache_data(ttl=60)
def load_all_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 1. Cargar pestaña 'Movimientos'
    try:
        df_mov = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Movimientos", ttl="1m")
        df_mov['Fecha'] = pd.to_datetime(df_mov['Fecha'])
        df_mov['Importe'] = pd.to_numeric(df_mov['Importe'])
    except Exception:
        # Si la pestaña aún no existe con ese nombre, lee la primera hoja
        df_mov = conn.read(spreadsheet=SPREADSHEET_URL, ttl="1m")
        df_mov['Fecha'] = pd.to_datetime(df_mov['Fecha'])
        df_mov['Importe'] = pd.to_numeric(df_mov['Importe'])

    # 2. Cargar pestaña 'Categorías'
    try:
        df_cat = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Categorías", ttl="1m")
    except Exception:
        df_cat = pd.DataFrame({
            "Categoría Principal": ["Ingresos Operativos", "Gastos de Personal", "Gastos Operativos", "Gastos Financieros", "Impuestos y Tasas"],
            "Subcategoría": ["Ventas", "Nóminas", "Alquileres", "Comisiones", "IVA"],
            "Tipo": ["Ingreso", "Gasto", "Gasto", "Gasto", "Gasto"]
        })

    return df_mov, df_cat

try:
    df, df_cat = load_all_data()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# --- SIDEBAR: FILTROS Y CARGA DE EXCEL ---
st.sidebar.header("📁 Importar Extracto Bancario")

uploaded_file = st.sidebar.file_uploader("Subir archivo Excel o CSV", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    banco_origen = st.sidebar.selectbox("Banco del extracto", ["BBVA Principal", "CaixaBank", "Otro"])
    
    if st.sidebar.button("Procesar y Volcar a Google Sheets"):
        try:
            if uploaded_file.name.endswith(".csv"):
                df_excel = pd.read_csv(uploaded_file)
            else:
                df_excel = pd.read_excel(uploaded_file)
            
            # Normalizar columnas (Adaptar según nombres del extracto del banco)
            # Asume columnas estándar o detecta Fecha, Concepto e Importe
            nuevos_registros = []
            start_id = len(df) + 1
            
            for idx, row in df_excel.iterrows():
                # Extracción flexible de columnas según el banco
                fecha_val = row.get("Fecha") or row.get("Fecha Valor") or row.get("F.Operación")
                concepto_val = row.get("Concepto") or row.get("Descripción") or row.get("Leyenda") or "Movimiento Importado"
                importe_val = row.get("Importe") or row.get("Monto") or 0.0
                
                importe_float = float(importe_val)
                tipo_val = "Ingreso" if importe_float >= 0 else "Gasto"
                
                nuevos_registros.append({
                    "ID_Movimiento": f"MOV-{start_id + idx:04d}",
                    "Fecha": str(pd.to_datetime(fecha_val).date()) if pd.notnull(fecha_val) else str(pd.Timestamp.now().date()),
                    "Cuenta / Banco": banco_origen,
                    "Concepto / Descripción": str(concepto_val),
                    "Tipo": tipo_val,
                    "Categoría": "Sin Categorizar",
                    "Subcategoría": "Pendiente",
                    "Importe": importe_float,
                    "Estado": "Pendiente",
                    "Notas / Observaciones": f"Importado desde {uploaded_file.name}"
                })
            
            df_nuevos = pd.DataFrame(nuevos_registros)
            df_actualizado = pd.concat([df, df_nuevos], ignore_index=True)
            
            # Volcar exclusivamente en la pestaña Movimientos
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Movimientos", data=df_actualizado)
            
            st.sidebar.success(f"¡{len(df_nuevos)} movimientos volcados correctamente a 'Movimientos'!")
            st.cache_data.clear()
            st.rerun()
            
        except Exception as err:
            st.sidebar.error(f"Error al procesar el archivo: {err}")

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filtros")

bancos = ["Todos"] + sorted(list(df["Cuenta / Banco"].dropna().unique()))
banco_sel = st.sidebar.selectbox("Cuenta / Banco", bancos)

categorias = ["Todas"] + sorted(list(df["Categoría"].dropna().unique()))
cat_sel = st.sidebar.selectbox("Categoría", categorias)

# Aplicar Filtros
df_filtered = df.copy()
if banco_sel != "Todos":
    df_filtered = df_filtered[df_filtered["Cuenta / Banco"] == banco_sel]
if cat_sel != "Todas":
    df_filtered = df_filtered[df_filtered["Categoría"] == cat_sel]

# --- DASHBOARD & KPIS ---
ingresos = df_filtered[df_filtered["Importe"] > 0]["Importe"].sum()
gastos = df_filtered[df_filtered["Importe"] < 0]["Importe"].sum()
balance = ingresos + gastos

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ingresos Totales", f"{ingresos:,.2f} €")
col2.metric("Gastos Totales", f"{abs(gastos):,.2f} €")
col3.metric("Balance Neto", f"{balance:,.2f} €")
col4.metric("Nº Transacciones", len(df_filtered))

st.markdown("---")

# Visualizaciones y Tabla
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("📊 Gastos por Categoría")
    df_gastos = df_filtered[df_filtered["Importe"] < 0].copy()
    if not df_gastos.empty:
        df_gastos["Importe_Abs"] = df_gastos["Importe"].abs()
        fig_cat = px.pie(df_gastos, values="Importe_Abs", names="Categoría", hole=0.4)
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("Sin datos de gastos.")

with col_chart2:
    st.subheader("📈 Flujo de Caja")
    df_trend = df_filtered.sort_values("Fecha")
    if not df_trend.empty:
        fig_line = px.bar(df_trend, x="Fecha", y="Importe", color="Tipo", color_discrete_map={"Ingreso": "#2ecc71", "Gasto": "#e74c3c"})
        st.plotly_chart(fig_line, use_container_width=True)

st.subheader("📋 Base de Datos de Movimientos (`Movimientos`)")
st.dataframe(df_filtered.style.format({"Importe": "{:,.2f} €"}), use_container_width=True, hide_index=True)
