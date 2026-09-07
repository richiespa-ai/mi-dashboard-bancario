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
# Pega aquí tu URL de Google Apps Script (/exec)
APPS_SCRIPT_URL = "TU_URL_DE_GOOGLE_APPS_SCRIPT_AQUI"

def limpiar_importe(val):
    """Convierte formatos de importe españoles/internacionales a float de forma robusta."""
    if pd.isna(val):
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

@st.cache_data(ttl=60)
def load_all_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 1. Cargar pestaña 'Movimientos'
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
        df_mov['Importe'] = df_mov['Importe'].apply(limpiar_importe)

    # 2. Cargar pestaña 'Categorías'
    try:
        df_cat = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Categorías", ttl="1m")
    except Exception:
        df_cat = pd.DataFrame(columns=["Categoría Principal", "Subcategoría", "Tipo", "Palabras Clave"])

    return df_mov, df_cat

try:
    df, df_cat = load_all_data()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

def categorizar_concepto(concepto, df_cat):
    """Asigna categoría basándose en palabras clave de la tabla de categorías."""
    if df_cat.empty or not concepto:
        return "Sin Categorizar", "General"
    
    concepto_lower = str(concepto).lower()
    for _, row in df_cat.iterrows():
        # Si la tabla tiene columna de palabras clave o usa la propia subcategoría/categoría
        keywords = str(row.get("Palabras Clave", row.get("Subcategoría", ""))).lower()
        cat_principal = row.get("Categoría Principal", "Otros")
        subcat = row.get("Subcategoría", "General")
        
        if keywords and any(kw.strip() in concepto_lower for kw in keywords.split(",")):
            return cat_principal, subcat
            
    return "Sin Categorizar", "Pendiente"

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
                    
                    importe_float = limpiar_importe(importe_val)
                    importe_float = round(importe_float, 2)
                    
                    fecha_dt = pd.to_datetime(fecha_val, errors='coerce')
                    fecha_str = str(fecha_dt.date()) if pd.notnull(fecha_dt) else str(pd.Timestamp.now().date())
                    tipo_val = "Ingreso" if importe_float >= 0 else "Gasto"
                    
                    # Categorización automática con la tabla de categorías
                    cat_calc, subcat_calc = categorizar_concepto(concepto_val, df_cat)
                    
                    fila_tabla = [
                        f"MOV-{start_id + len(nuevas_filas):04d}",
                        fecha_str,
                        "Banco Importado",
                        str(concepto_val),
                        tipo_val,
                        cat_calc,
                        subcat_calc,
                        importe_float,
                        "Pendiente",
                        f"Importado de {uploaded_file.name}"
                    ]
                    nuevas_filas.append(fila_tabla)
                
                if nuevas_filas:
                    response = requests.post(APPS_SCRIPT_URL, json={"rows": nuevas_filas})
                    if response.status_code == 200:
                        st.sidebar.success(f"¡{len(nuevas_filas)} movimientos guardados en Google Sheets!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.sidebar.error(f"Error al sincronizar con Google Sheets: {response.text}")
                else:
                    st.sidebar.warning("No hay filas válidas en el archivo.")
                    
            except Exception as err:
                st.sidebar.error(f"Error procesando el archivo: {err}")

st.sidebar.markdown("---")

# --- SIDEBAR: FILTROS ---
st.sidebar.header("🔍 Filtros")

bancos = ["Todos"] + sorted(list(df["Cuenta / Banco"].dropna().unique())) if not df.empty else ["Todos"]
banco_sel = st.sidebar.selectbox("Cuenta / Banco", bancos)

categorias = ["Todas"] + sorted(list(df["Categoría"].dropna().unique())) if not df.empty else ["Todas"]
cat_sel = st.sidebar.selectbox("Categoría", categorias)

# Aplicar Filtros
df_filtered = df.copy()
if not df_filtered.empty:
    if banco_sel != "Todos":
        df_filtered = df_filtered[df_filtered["Cuenta / Banco"] == banco_sel]
    if cat_sel != "Todas":
        df_filtered = df_filtered[df_filtered["Categoría"] == cat_sel]

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
            st.info("No hay gastos registrados en la selección actual.")
    else:
        st.info("La base de datos de movimientos está vacía.")

with col_chart2:
    st.subheader("📈 Flujo de Caja")
    if not df_filtered.empty:
        df_trend = df_filtered.dropna(subset=["Fecha"]).sort_values("Fecha")
        if not df_trend.empty:
            fig_line = px.bar(
                df_trend,
                x="Fecha",
                y="Importe",
                color="Tipo",
                color_discrete_map={"Ingreso": "#2ecc71", "Gasto": "#e74c3c"}
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("No hay fechas válidas para mostrar el gráfico.")
    else:
        st.info("La base de datos de movimientos está vacía.")

st.markdown("---")

# --- TABLA DE DATOS FORMATEADA ---
st.subheader("📋 Registro de Movimientos (`Movimientos`)")
if not df_filtered.empty:
    df_mostrar = df_filtered.copy()
    df_mostrar['Fecha'] = df_mostrar['Fecha'].dt.strftime('%Y-%m-%d')
    st.dataframe(
        df_mostrar.style.format({"Importe": "{:,.2f} €"}),
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("No hay movimientos registrados. Sube un extracto bancario en el menú lateral.")
