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
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxRDfF6PNIe985d984QHbSP66gBVaD3TJWgEKBvZPzkt9N_PtIa63AN-9dgwrJamV4NCA/exec"

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

@st.cache_data(ttl=10)
def load_all_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    cols_esperadas = ["Fecha", "Concepto", "Categoría", "Importe"]
    
    try:
        df_mov = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Movimientos", ttl=0)
    except Exception:
        df_mov = pd.DataFrame(columns=cols_esperadas)

    if df_mov is None or df_mov.empty:
        df_mov = pd.DataFrame(columns=cols_esperadas)
    else:
        df_mov.columns = [str(c).strip() for c in df_mov.columns]
        for col in cols_esperadas:
            if col not in df_mov.columns:
                df_mov[col] = None
        
        df_mov['Importe'] = df_mov['Importe'].apply(limpiar_importe)
        df_mov['Importe'] = pd.to_numeric(df_mov['Importe'], errors='coerce').fillna(0.0)
        df_mov['Fecha'] = pd.to_datetime(df_mov['Fecha'], errors='coerce')

    try:
        df_cat = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Categorías", ttl=0)
        if df_cat is not None and not df_cat.empty:
            df_cat.columns = [str(c).strip() for c in df_cat.columns]
        else:
            df_cat = pd.DataFrame(columns=["Categoría Principal", "Subcategoría"])
    except Exception:
        df_cat = pd.DataFrame(columns=["Categoría Principal", "Subcategoría"])

    return df_mov, df_cat

df, df_cat = load_all_data()

def categorizar_concepto(concepto, df_cat):
    if df_cat.empty or not concepto:
        return "Sin Categorizar"
    concepto_lower = str(concepto).lower()
    for _, row in df_cat.iterrows():
        subcat = str(row.get("Subcategoría", ""))
        cat_principal = str(row.get("Categoría Principal", "Otros"))
        if subcat and subcat.lower() in concepto_lower:
            return cat_principal
    return "Sin Categorizar"

def procesar_extracto_bancario(uploaded_file):
    """Lee el excel sin cabecera fija, detecta dónde empiezan los datos y extrae por posición (A, C, D)."""
    if uploaded_file.name.endswith(".csv"):
        df_raw = pd.read_csv(uploaded_file, header=None)
    else:
        df_raw = pd.read_excel(uploaded_file, header=None)
    
    fila_inicio = 0
    # Buscar dinámicamente la fila de cabecera o datos buscando la palabra 'Fecha' o 'Operación'
    for idx, row in df_raw.iterrows():
        fila_str = " ".join([str(val).lower() for val in row.values if pd.notna(val)])
        if "fecha" in fila_str or "operacion" in fila_str or "concepto" in fila_str:
            fila_inicio = idx + 1  # Los datos empiezan justo debajo de la cabecera
            break
            
    # Si no encuentra cabecera clara, asumimos que los datos empiezan en la primera fila con valores válidos
    if fila_inicio >= len(df_raw):
        fila_inicio = 0

    df_datos = df_raw.iloc[fila_inicio:].copy()
    
    filas_procesadas = []
    for _, row in df_datos.iterrows():
        vals = row.values
        # Asegurarnos de que la fila tiene suficientes columnas (A=0, C=2, D=3)
        if len(vals) < 4:
            continue
            
        fecha_val = vals[0]     # Columna A: Fecha de Operación
        concepto_val = vals[2]  # Columna C: Concepto
        importe_val = vals[3]   # Columna D: Importe
        
        # Validar que al menos la fecha o el importe tengan sentido para descartar filas vacías o de resumen
        if pd.isna(fecha_val) or pd.isna(importe_val):
            continue
            
        importe_float = limpiar_importe(importe_val)
        if importe_float == 0.0 and (pd.isna(concepto_val) or str(concepto_val).strip() == ""):
            continue
            
        importe_float = round(importe_float, 2)
        
        fecha_dt = pd.to_datetime(fecha_val, errors='coerce')
        if pd.isna(fecha_dt):
            continue # Si no es una fecha válida, descartamos la fila (evita cabeceras repetidas)
            
        fecha_str = str(fecha_dt.date())
        cat_val = categorizar_concepto(concepto_val, df_cat)
        
        filas_procesadas.append([
            fecha_str,
            str(concepto_val).strip(),
            cat_val,
            importe_float
        ])
        
    return filas_procesadas

# --- SIDEBAR: CARGA DE EXCEL ---
st.sidebar.header("📁 Importar Extracto")
uploaded_file = st.sidebar.file_uploader("Subir archivo (Excel o CSV)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    if st.sidebar.button("Volcar a Google Sheets"):
        if APPS_SCRIPT_URL == "TU_URL_DE_GOOGLE_APPS_SCRIPT_AQUI" or not APPS_SCRIPT_URL.startswith("https://"):
            st.sidebar.error("❌ Configura tu URL de Google Apps Script en el código.")
        else:
            try:
                nuevas_filas = procesar_extracto_bancario(uploaded_file)
                
                if nuevas_filas:
                    response = requests.post(APPS_SCRIPT_URL, json={"rows": nuevas_filas})
                    if response.status_code == 200:
                        st.sidebar.success(f"¡{len(nuevas_filas)} movimientos guardados correctamente!")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.sidebar.error(f"Error en Apps Script: {response.text}")
                else:
                    st.sidebar.warning("No se han encontrado filas de movimientos válidas en el archivo.")
            except Exception as err:
                st.sidebar.error(f"Error procesando el fichero: {err}")

st.sidebar.markdown("---")

# --- SIDEBAR: FILTROS ---
st.sidebar.header("🔍 Filtros")

categorias = ["Todas"] + sorted(list(df["Categoría"].dropna().unique())) if not df.empty else ["Todas"]
cat_sel = st.sidebar.selectbox("Categoría", categorias)

df_filtered = df.copy()
if not df_filtered.empty:
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
            st.info("No hay gastos registrados.")
    else:
        st.info("Base de datos vacía.")

with col_chart2:
    st.subheader("📈 Flujo de Caja")
    if not df_filtered.empty:
        df_trend = df_filtered.dropna(subset=["Fecha"]).sort_values("Fecha")
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
            st.info("No hay fechas válidas.")
    else:
        st.info("Base de datos vacía.")

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
    st.warning("No hay movimientos registrados.")
