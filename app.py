import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date

st.set_page_config(
    page_title="Dashboard Bancario",
    page_icon="🏦",
    layout="wide"
)

st.title("🏦 Dashboard Bancario y Control de Finanzas")

# --- FUNCIONES DE UTILIDAD ---
def limpiar_importe(val):
    if pd.isna(val) or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace("€", "").replace(" ", "").strip()
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

def categorizar_concepto(concepto):
    if not concepto:
        return "Otros"
    c = str(concepto).lower()
    if any(w in c for w in ["supermercado", "mercadona", "carrefour", "dia", "lidl", "aldi", "alimentacion"]):
        return "Alimentación"
    elif any(w in c for w in ["gasolina", "repsol", "cepsa", "transporte", "metro", "renfe", "uber", "cabify"]):
        return "Transporte"
    elif any(w in c for w in ["restaurante", "bar", "cafe", "mcdonalds", "glovo", "uber eats"]):
        return "Ocio y Restaurantes"
    elif any(w in c for w in ["luz", "agua", "gas", "iberdrola", "endesa", "alquiler", "comunidad", "netflix", "spotify"]):
        return "Vivienda y Suministros"
    elif any(w in c for w in ["nomina", "sueldo", "transferencia", "ingreso"]):
        return "Ingresos"
    return "Otros"

def procesar_extracto_bancario(uploaded_file):
    if uploaded_file.name.endswith(".csv"):
        df_raw = pd.read_csv(uploaded_file, header=None)
    else:
        df_raw = pd.read_excel(uploaded_file, header=None)
    
    fila_inicio = 0
    for idx, row in df_raw.iterrows():
        fila_str = " ".join([str(val).lower() for val in row.values if pd.notna(val)])
        if "fecha" in fila_str or "operacion" in fila_str or "concepto" in fila_str:
            fila_inicio = idx + 1
            break

    df_datos = df_raw.iloc[fila_inicio:].copy()
    
    registros = []
    for _, row in df_datos.iterrows():
        vals = row.values
        if len(vals) < 4:
            continue
            
        fecha_val = vals[0]     # Columna A: Fecha
        concepto_val = vals[2]  # Columna C: Concepto
        importe_val = vals[3]   # Columna D: Importe
        
        if pd.isna(fecha_val) or pd.isna(importe_val):
            continue
            
        importe_float = limpiar_importe(importe_val)
        if importe_float == 0.0 and (pd.isna(concepto_val) or str(concepto_val).strip() == ""):
            continue
            
        importe_float = round(importe_float, 2)
        
        fecha_dt = pd.to_datetime(fecha_val, errors='coerce')
        if pd.isna(fecha_dt):
            continue
            
        fecha_str = str(fecha_dt.date())
        cat_val = categorizar_concepto(concepto_val)
        
        registros.append({
            "Fecha": fecha_str,
            "Concepto": str(concepto_val).strip(),
            "Categoría": cat_val,
            "Importe": importe_float
        })
        
    return pd.DataFrame(registros)

# --- GESTIÓN DE ESTADO (SESSION STATE) ---
if "df_movimientos" not in st.session_state:
    st.session_state.df_movimientos = pd.DataFrame(columns=["Fecha", "Concepto", "Categoría", "Importe"])

# --- SIDEBAR: CARGA DE ARCHIVO ---
st.sidebar.header("📁 Importar Extracto")
uploaded_file = st.sidebar.file_uploader("Subir archivo (Excel o CSV)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    if st.sidebar.button("Procesar y Cargar en la App"):
        try:
            df_nuevo = procesar_extracto_bancario(uploaded_file)
            if not df_nuevo.empty:
                st.session_state.df_movimientos = df_nuevo
                st.sidebar.success(f"¡Se han cargado {len(df_nuevo)} movimientos correctamente!")
            else:
                st.sidebar.warning("No se encontraron movimientos válidos en las columnas A, C y D.")
        except Exception as err:
            st.sidebar.error(f"Error procesando el archivo: {err}")

st.sidebar.markdown("---")

# Obtener el DataFrame actual del estado
df = st.session_state.df_movimientos

# Asegurar formato de fecha datetime para filtros
if not df.empty and "Fecha" in df.columns:
    df["Fecha_dt"] = pd.to_datetime(df["Fecha"], errors="coerce")
else:
    df["Fecha_dt"] = pd.Series(dtype="datetime64[ns]")

# --- SIDEBAR: FILTROS AVANZADOS ---
st.sidebar.header("🔍 Filtros Avanzados")

# 1. Filtro de Categoría
if not df.empty and "Categoría" in df.columns:
    lista_categorias = sorted(list(df["Categoría"].dropna().unique()))
    categorias_opciones = ["Todas"] + lista_categorias
else:
    categorias_opciones = ["Todas"]

cat_sel = st.sidebar.selectbox("Categoría", categorias_opciones, key="filtro_categoria")

# 2. Filtro de Tiempo
modo_tiempo = st.sidebar.radio(
    "Periodo de tiempo", 
    ["Todo el histórico", "Mes actual", "Mes anterior", "Rango personalizado"],
    key="filtro_modo_tiempo"
)

# Copia para filtrar
df_filtered = df.copy()

if not df_filtered.empty:
    # Aplicar categoría
    if cat_sel != "Todas":
        df_filtered = df_filtered[df_filtered["Categoría"] == cat_sel]
    
    # Aplicar tiempo
    hoy = pd.Timestamp.today()
    if modo_tiempo == "Mes actual":
        df_filtered = df_filtered[(df_filtered["Fecha_dt"].dt.year == hoy.year) & (df_filtered["Fecha_dt"].dt.month == hoy.month)]
    elif modo_tiempo == "Mes anterior":
        mes_ant = hoy.month - 1 if hoy.month > 1 else 12
        anio_ant = hoy.year if hoy.month > 1 else hoy.year - 1
        df_filtered = df_filtered[(df_filtered["Fecha_dt"].dt.year == anio_ant) & (df_filtered["Fecha_dt"].dt.month == mes_ant)]
    elif modo_tiempo == "Rango personalizado":
        col_f1, col_f2 = st.sidebar.columns(2)
        with col_f1:
            f_inicio = st.date_input("Desde", value=date(hoy.year, 1, 1), key="fecha_desde")
        with col_f2:
            f_fin = st.date_input("Hasta", value=hoy.date(), key="fecha_hasta")
            
        inicio = pd.to_datetime(f_inicio)
        fin = pd.to_datetime(f_fin)
        df_filtered = df_filtered[(df_filtered["Fecha_dt"] >= inicio) & (df_filtered["Fecha_dt"] <= fin)]

    df_filtered["Importe"] = pd.to_numeric(df_filtered["Importe"], errors="coerce").fillna(0.0)

# --- DASHBOARD DE KPIS ---
ingresos = df_filtered[df_filtered["Importe"] > 0]["Importe"].sum() if not df_filtered.empty else 0.0
gastos = df_filtered[df_filtered["Importe"] < 0]["Importe"].sum() if not df_filtered.empty else 0.0
balance = ingresos + gastos

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ingresos Totales", f"{ingresos:,.2f} €")
col2.metric("Gastos Totales", f"{abs(gastos):,.2f} €")
col3.metric("Balance Neto", f"{balance:,.2f} €")
col4.metric("Nº Transacciones", len(df_filtered))

st.markdown("---")

# --- SECCIÓN: PRÓXIMOS RECIBOS / ÚLTIMOS MOVIMIENTOS ---
if not df.empty:
    st.subheader("📅 Últimos Movimientos del Mes")
    df_recientes = df.sort_values(by="Fecha_dt", ascending=False).head(5)
    cols_mostrar_recientes = df_recientes[["Fecha", "Concepto", "Categoría", "Importe"]].copy()
    cols_mostrar_recientes["Importe"] = cols_mostrar_recientes["Importe"].apply(lambda x: f"{x:,.2f} €")
    st.dataframe(cols_mostrar_recientes, use_container_width=True, hide_index=True)

st.markdown("---")

# --- GRÁFICOS ---
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("📊 Gastos por Categoría")
    if not df_filtered.empty:
        df_gastos = df_filtered[df_filtered["Importe"] < 0].copy()
        if not df_gastos.empty:
            df_gastos["Importe_Abs"] = df_gastos["Importe"].abs()
            fig_cat = px.pie(df_gastos, values="Importe_Abs", names="Categoría", hole=0.4)
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("No hay gastos registrados para este filtro.")
    else:
        st.info("Sube un archivo para ver los gráficos.")

with col_chart2:
    st.subheader("📈 Flujo de Caja por Fecha")
    if not df_filtered.empty:
        df_trend = df_filtered.dropna(subset=["Fecha_dt"]).sort_values("Fecha_dt")
        if not df_trend.empty:
            df_trend["Tipo"] = df_trend["Importe"].apply(lambda x: "Ingreso" if x >= 0 else "Gasto")
            fig_line = px.bar(
                df_trend,
                x="Fecha",
                y="Importe",
                color="Tipo",
                color_discrete_map={"Ingreso": "#2ecc71", "Gasto": "#e74c3c"}
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("No hay fechas válidas para este filtro.")
    else:
        st.info("Sube un archivo para ver el flujo de caja.")

st.markdown("---")

# --- TABLA DE DATOS FILTRADOS ---
st.subheader("📋 Registro Completo (Filtrado)")
if not df_filtered.empty:
    df_mostrar = df_filtered[["Fecha", "Concepto", "Categoría", "Importe"]].copy()
    st.dataframe(
        df_mostrar.style.format({"Importe": "{:,.2f} €"}),
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("No hay movimientos cargados o para los filtros seleccionados. Por favor, sube tu archivo en el menú lateral.")
