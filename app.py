import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, date

st.set_page_config(
    page_title="Dashboard Bancario",
    page_icon="🏦",
    layout="wide"
)

st.title("🏦 Dashboard Bancario y Control de Finanzas")

# --- URL DE GOOGLE APPS SCRIPT ---
APPS_SCRIPT_URL = "https://script.google.com/macros/library/d/1Inca7JqdR4v1X5yCQCF6CuAFumpyo-stOpH8T8BCq5YYYVWVwoscVs_O/2"

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
            
        fecha_val = vals[0]     # Columna A
        concepto_val = vals[2]  # Columna C
        importe_val = vals[3]   # Columna D
        
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

# --- TUS FUNCIONES DE UTILIDAD (limpiar_importe, categorizar_concepto, etc.) ---
# ... (estas las dejas tal cual están más arriba) ...

# --- AQUÍ ES DONDE SUSTITUYES EL BLOQUE ---
if "df_movimientos" not in st.session_state:
    df_inicial = pd.DataFrame(columns=["Fecha", "Concepto", "Categoría", "Importe"])
    
    if APPS_SCRIPT_URL != "TU_URL_DE_GOOGLE_APPS_SCRIPT_AQUI" and APPS_SCRIPT_URL.startswith("https://"):
        try:
            response = requests.get(APPS_SCRIPT_URL, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data:
                    df_temp = pd.DataFrame(data)
                    
                    # Limpiar cabeceras si vienen en la primera fila del Sheet
                    if len(df_temp) > 1 and any(str(val).lower() in ["fecha", "concepto", "importe"] for val in df_temp.iloc[0].values):
                        df_temp.columns = df_temp.iloc[0]
                        df_temp = df_temp.drop(0).reset_index(drop=True)
                    
                    cols_lower = [str(c).lower() for c in df_temp.columns]
                    
                    col_fecha = next((df_temp.columns[i] for i, c in enumerate(cols_lower) if "fecha" in c), df_temp.columns[0] if len(df_temp.columns) > 0 else None)
                    col_concepto = next((df_temp.columns[i] for i, c in enumerate(cols_lower) if "concepto" in c or "descrip" in c), df_temp.columns[2] if len(df_temp.columns) > 2 else None)
                    col_importe = next((df_temp.columns[i] for i, c in enumerate(cols_lower) if "importe" in c or "cantidad" in c), df_temp.columns[3] if len(df_temp.columns) > 3 else None)
                    col_categoria = next((df_temp.columns[i] for i, c in enumerate(cols_lower) if "categor" in c), None)

                    if col_fecha is not None and col_importe is not None:
                        registros_sheet = []
                        for _, row in df_temp.iterrows():
                            f_val = row[col_fecha]
                            c_val = row[col_concepto] if col_concepto else ""
                            i_val = row[col_importe]
                            cat_val = row[col_categoria] if col_categoria and pd.notna(row[col_categoria]) else None
                            
                            if pd.isna(f_val) or pd.isna(i_val):
                                continue
                                
                            importe_float = limpiar_importe(i_val)
                            fecha_dt = pd.to_datetime(f_val, errors='coerce')
                            if pd.isna(fecha_dt):
                                continue
                                
                            if not cat_val or str(cat_val).strip() == "":
                                cat_val = categorizar_concepto(c_val)
                                
                            registros_sheet.append({
                                "Fecha": str(fecha_dt.date()),
                                "Concepto": str(c_val).strip(),
                                "Categoría": str(cat_val).strip(),
                                "Importe": round(importe_float, 2)
                            })
                        if registros_sheet:
                            df_inicial = pd.DataFrame(registros_sheet)
        except Exception as e:
            st.sidebar.error(f"Error conectando al Sheet: {e}")
            
    st.session_state.df_movimientos = df_inicial

# --- A PARTIR DE AQUÍ SIGUE EL RESTO DE TU CÓDIGO (Sidebar de archivos, filtros, etc.) ---
# --- SIDEBAR: CARGA DE ARCHIVO ---
st.sidebar.header("📁 Importar Extracto")
uploaded_file = st.sidebar.file_uploader("Subir archivo (Excel o CSV)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    if st.sidebar.button("Procesar y Cargar"):
        try:
            df_nuevo = procesar_extracto_bancario(uploaded_file)
            if not df_nuevo.empty:
                st.session_state.df_movimientos = pd.concat([st.session_state.df_movimientos, df_nuevo], ignore_index=True).drop_duplicates()
                st.sidebar.success(f"¡Se han añadido {len(df_nuevo)} movimientos!")
                st.rerun()
            else:
                st.sidebar.warning("No se encontraron movimientos válidos.")
        except Exception as err:
            st.sidebar.error(f"Error: {err}")

st.sidebar.markdown("---")

# --- OBTENCIÓN Y PREPARACIÓN DE DATOS ---
df = st.session_state.df_movimientos.copy()

if not df.empty and "Fecha" in df.columns:
    df["Fecha_dt"] = pd.to_datetime(df["Fecha"], errors="coerce")
else:
    df["Fecha_dt"] = pd.Series(dtype="datetime64[ns]")

# --- SIDEBAR: FILTROS (DEFINIDOS SIEMPRE DE FORMA ESTÁTICA) ---
st.sidebar.header("🔍 Filtros Avanzados")

# 1. Categorías seguras (siempre muestra opciones predeterminadas + las que existan)
categorias_base = ["Todas", "Alimentación", "Transporte", "Ocio y Restaurantes", "Vivienda y Suministros", "Ingresos", "Otros"]
if not df.empty and "Categoría" in df.columns:
    cats_en_df = df["Categoría"].dropna().unique().tolist()
    lista_categorias = sorted(list(set(categorias_base + [str(c) for c in cats_en_df])))
else:
    lista_categorias = categorias_base

cat_sel = st.sidebar.selectbox("Categoría", lista_categorias, key="filtro_categoria")

# 2. Periodo de tiempo estático
modo_tiempo = st.sidebar.radio(
    "Periodo de tiempo", 
    ["Todo el histórico", "Mes actual", "Mes anterior", "Rango personalizado"],
    key="filtro_modo_tiempo"
)

# 3. Calendarios siempre presentes en la barra lateral para evitar bloqueos de UI
st.sidebar.markdown("---")
st.sidebar.subheader("📅 Rango de Fechas")
hoy = pd.Timestamp.today()
f_inicio = st.sidebar.date_input("Desde", value=date(hoy.year, 1, 1), key="fecha_desde")
f_fin = st.sidebar.date_input("Hasta", value=hoy.date(), key="fecha_hasta")

# --- APLICACIÓN DE FILTROS ---
df_filtered = df.copy()

if not df_filtered.empty:
    # Filtro Categoría
    if cat_sel != "Todas":
        df_filtered = df_filtered[df_filtered["Categoría"] == cat_sel]
    
    # Filtro Tiempo
    if modo_tiempo == "Mes actual":
        df_filtered = df_filtered[(df_filtered["Fecha_dt"].dt.year == hoy.year) & (df_filtered["Fecha_dt"].dt.month == hoy.month)]
    elif modo_tiempo == "Mes anterior":
        mes_ant = hoy.month - 1 if hoy.month > 1 else 12
        anio_ant = hoy.year if hoy.month > 1 else hoy.year - 1
        df_filtered = df_filtered[(df_filtered["Fecha_dt"].dt.year == anio_ant) & (df_filtered["Fecha_dt"].dt.month == mes_ant)]
    elif modo_tiempo == "Rango personalizado":
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

# --- ÚLTIMOS MOVIMIENTOS ---
if not df.empty:
    st.subheader("📅 Últimos Movimientos")
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
        st.info("No hay datos cargados para mostrar gráficos.")

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
        st.info("No hay datos cargados para mostrar el flujo de caja.")

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
    st.warning("No hay movimientos cargados o que coincidan con los filtros seleccionados.")
