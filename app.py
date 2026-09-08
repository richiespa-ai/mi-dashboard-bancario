import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime

st.set_page_config(
    page_title="Dashboard Bancario",
    page_icon="🏦",
    layout="wide"
)

st.title("🏦 Dashboard Bancario y Control de Finanzas")

# URL de tu Google Apps Script
APPS_SCRIPT_URL = "TU_URL_DE_GOOGLE_APPS_SCRIPT_AQUI"

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

# --- GESTIÓN DE ESTADO ---
if "df_movimientos" not in st.session_state:
    st.session_state.df_movimientos = pd.DataFrame(columns=["Fecha", "Concepto", "Categoría", "Importe"])

# --- SIDEBAR: CARGA DE EXCEL ---
st.sidebar.header("📁 Importar Extracto")
uploaded_file = st.sidebar.file_uploader("Subir archivo (Excel o CSV)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    if st.sidebar.button("Cargar y Sincronizar Nuevos Movimientos"):
        if APPS_SCRIPT_URL == "TU_URL_DE_GOOGLE_APPS_SCRIPT_AQUI" or not APPS_SCRIPT_URL.startswith("https://"):
            st.sidebar.error("❌ Configura primero tu URL de Google Apps Script.")
        else:
            try:
                df_nuevo = procesar_extracto_bancario(uploaded_file)
                if not df_nuevo.empty:
                    df_actual = st.session_state.df_movimientos
                    
                    if df_actual.empty:
                        df_a_incorporar = df_nuevo
                    else:
                        df_actual["clave_unitaria"] = df_actual["Fecha"].astype(str) + "_" + df_actual["Concepto"].astype(str) + "_" + df_actual["Importe"].astype(str)
                        df_nuevo["clave_unitaria"] = df_nuevo["Fecha"].astype(str) + "_" + df_nuevo["Concepto"].astype(str) + "_" + df_nuevo["Importe"].astype(str)
                        
                        df_a_incorporar = df_nuevo[~df_nuevo["clave_unitaria"].isin(df_actual["clave_unitaria"])].drop(columns=["clave_unitaria"])
                        df_actual = df_actual.drop(columns=["clave_unitaria"])
                    
                    if not df_a_incorporar.empty:
                        nuevos_datos_lista = df_a_incorporar.values.tolist()
                        response = requests.post(APPS_SCRIPT_URL, json={"rows": nuevos_datos_lista})
                        
                        if response.status_code == 200:
                            st.session_state.df_movimientos = pd.concat([df_actual, df_a_incorporar], ignore_index=True)
                            st.sidebar.success(f"¡Se añadieron {len(df_a_incorporar)} movimientos nuevos!")
                        else:
                            st.sidebar.error(f"Error al sincronizar con Google Sheets: {response.text}")
                    else:
                        st.sidebar.warning("⚠️ Todos los movimientos de este archivo ya estaban registrados.")
                else:
                    st.sidebar.warning("No se encontraron movimientos válidos en las columnas A, C y D.")
            except Exception as err:
                st.sidebar.error(f"Error procesando el archivo: {err}")

st.sidebar.markdown("---")

df = st.session_state.df_movimientos

# Asegurar formato de fecha en el DataFrame maestro
if not df.empty:
    df["Fecha_dt"] = pd.to_datetime(df["Fecha"], errors="coerce")
else:
    df["Fecha_dt"] = pd.Series(dtype="datetime64[ns]")

# --- SIDEBAR: FILTROS TEMPORALES Y DE CATEGORÍA ---
st.sidebar.header("🔍 Filtros Avanzados")

# 1. Filtro de Categoría
categorias = ["Todas"] + sorted(list(df["Categoría"].dropna().unique())) if not df.empty else ["Todas"]
cat_sel = st.sidebar.selectbox("Categoría", categorias)

# 2. Filtro de Tiempo
modo_tiempo = st.sidebar.radio("Periodo de tiempo", ["Todo el histórico", "Mes actual", "Mes anterior", "Rango personalizado"])

df_filtered = df.copy()

if not df_filtered.empty:
    # Aplicar filtro de categoría
    if cat_sel != "Todas":
        df_filtered = df_filtered[df_filtered["Categoría"] == cat_sel]
    
    # Aplicar filtros temporales
    hoy = pd.Timestamp.today().date()
    
    if modo_tiempo == "Mes actual":
        df_filtered = df_filtered[(df_filtered["Fecha_dt"].dt.year == pd.Timestamp.today().year) & (df_filtered["Fecha_dt"].dt.month == pd.Timestamp.today().month)]
    elif modo_tiempo == "Mes anterior":
        mes_actual = pd.Timestamp.today().month
        anio_actual = pd.Timestamp.today().year
        mes_ant = mes_actual - 1 if mes_actual > 1 else 12
        anio_ant = anio_actual if mes_actual > 1 else anio_actual - 1
        df_filtered = df_filtered[(df_filtered["Fecha_dt"].dt.year == anio_ant) & (df_filtered["Fecha_dt"].dt.month == mes_ant)]
    elif modo_tiempo == "Rango personalizado":
        # Asegurar fechas mínimas y máximas válidas pasadas a .date()
        valid_dates = df_filtered["Fecha_dt"].dropna()
        if not valid_dates.empty:
            min_date = valid_dates.min().date()
            max_date = valid_dates.max().date()
        else:
            min_date = hoy
            max_date = hoy
            
        rango_fechas = st.sidebar.date_input(
            "Selecciona rango de fechas",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        
        if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
            inicio, fin = pd.to_datetime(rango_fechas[0]), pd.to_datetime(rango_fechas[1])
            df_filtered = df_filtered[(df_filtered["Fecha_dt"] >= inicio) & (df_filtered["Fecha_dt"] <= fin)]
        elif isinstance(rango_fechas, tuple) and len(rango_fechas) == 1:
            inicio = pd.to_datetime(rango_fechas[0])
            df_filtered = df_filtered[df_filtered["Fecha_dt"] >= inicio]

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

# --- SECCIÓN ADICIONAL: PRÓXIMOS RECIBOS O GASTOS RECIENTES DEL MES ---
if not df.empty:
    st.subheader("📅 Últimos Movimientos / Recibos del Mes")
    # Mostrar los gastos más recientes o del mes actual para ver los recibos que van entrando
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
            st.info("No hay gastos registrados en este filtro.")
    else:
        st.info("Sube un archivo Excel para ver los gráficos.")

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
            st.info("No hay fechas válidas en este filtro.")
    else:
        st.info("Sube un archivo Excel para ver el flujo de caja.")

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
    st.warning("No hay movimientos para los filtros seleccionados.")
