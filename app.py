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
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbx0W8sahQ29p0NTm9mxvIXWGvtLAdZsREWM__2nHXu2-Xgd9v3LRHUHT3OK8poHn84GRA/exec"

CATEGORIAS_BASE = [
    "Alimentación", "Transporte", "Ocio y Restaurantes", "Vivienda y Suministros",
    "Ingresos", "Farmacia", "Salud", "Seguros", "Préstamos", "Educación",
    "Impuestos y Tasas", "Garaje", "Otros"
]

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
    if any(w in c for w in ["supermercado", "mercadona", "carrefour", "dia", "lidl", "aldi", "alimentacion", "fruteria", "carniceria", "panaderia", "obrador", "tahona"]):
        return "Alimentación"
    elif any(w in c for w in ["gasolina", "repsol", "cepsa", "moeve", "transporte", "metro", "renfe", "uber", "cabify", "movilidad", "crtm", "parking"]):
        return "Transporte"
    elif any(w in c for w in ["restaurante", "bar", "cafe", "mcdonalds", "glovo", "uber eats"]):
        return "Ocio y Restaurantes"
    elif any(w in c for w in ["luz", "agua", "gas", "iberdrola", "endesa", "alquiler", "comunidad", "netflix", "spotify", "crunchyroll", "soundiiz", "lavanderia", "movil", "fibra", "securitas", "canal de i"]):
        return "Vivienda y Suministros"
    elif any(w in c for w in ["nomina", "sueldo", "transferencia", "ingreso", "devolucion"]):
        return "Ingresos"
    elif any(w in c for w in ["fcia.", "farmacia"]):
        return "Farmacia"
    elif any(w in c for w in ["psicolog", "clinica", "medico", "dentista"]):
        return "Salud"
    elif any(w in c for w in ["seguro", "metlife", "mapfre", "axa"]):
        return "Seguros"
    elif any(w in c for w in ["prestamo", "financiacion", "oney", "volkswagen"]):
        return "Préstamos"
    elif any(w in c for w in ["colegio", "fundacion", "escuela", "universidad"]):
        return "Educación"
    elif any(w in c for w in ["ayuntamiento", "tasa", "impuesto", "tributari"]):
        return "Impuestos y Tasas"
    elif "garaje" in c:
        return "Garaje"
    return "Otros"

def construir_mapa_categorias(df):
    """Concepto exacto (mayúsculas) -> última categoría usada para ese concepto."""
    mapa = {}
    if df is None or df.empty:
        return mapa
    for _, r in df.iterrows():
        clave = str(r.get("Concepto", "")).strip().upper()
        cat = r.get("Categoría")
        if clave and pd.notna(cat) and str(cat).strip():
            mapa[clave] = str(cat).strip()
    return mapa

def procesar_extracto_bancario(uploaded_file, mapa_categorias=None):
    mapa_categorias = mapa_categorias or {}
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
        concepto_limpio = str(concepto_val).strip()
        cat_val = mapa_categorias.get(concepto_limpio.upper()) or categorizar_concepto(concepto_val)

        registros.append({
            "Fecha": fecha_str,
            "Concepto": concepto_limpio,
            "Categoría": cat_val,
            "Importe": importe_float
        })

    return pd.DataFrame(registros)

def enviar_movimientos_a_sheet(df_nuevo):
    """Envía filas nuevas al Apps Script (doPost) para que las añada al Sheet sin duplicar."""
    filas = df_nuevo[["Fecha", "Concepto", "Categoría", "Importe"]].values.tolist()
    payload = {"rows": filas}
    response = requests.post(APPS_SCRIPT_URL, json=payload, timeout=15)
    response.raise_for_status()
    return response.json()

def actualizar_categorias_en_sheet(actualizaciones):
    """Actualiza la Categoría de movimientos ya existentes en el Sheet (por Fecha+Concepto+Importe)."""
    payload = {"action": "update_categoria", "updates": actualizaciones}
    response = requests.post(APPS_SCRIPT_URL, json=payload, timeout=15)
    response.raise_for_status()
    return response.json()

# --- CARGA INICIAL DESDE EL SHEET ---
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

# --- SIDEBAR: CARGA DE ARCHIVO ---
st.sidebar.header("📁 Importar Extracto")
uploaded_file = st.sidebar.file_uploader("Subir archivo (Excel o CSV)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    if st.sidebar.button("Procesar y Cargar"):
        try:
            mapa_categorias = construir_mapa_categorias(st.session_state.df_movimientos)
            df_nuevo = procesar_extracto_bancario(uploaded_file, mapa_categorias)
            if not df_nuevo.empty:
                df_actual = st.session_state.df_movimientos
                clave_actual = set(
                    (str(r["Fecha"]), str(r["Concepto"]), str(r["Importe"]))
                    for _, r in df_actual.iterrows()
                )
                df_nuevo["_clave"] = df_nuevo.apply(
                    lambda r: (str(r["Fecha"]), str(r["Concepto"]), str(r["Importe"])), axis=1
                )
                df_a_anadir = df_nuevo[~df_nuevo["_clave"].isin(clave_actual)].drop(columns=["_clave"])

                if not df_a_anadir.empty:
                    try:
                        resultado = enviar_movimientos_a_sheet(df_a_anadir)
                        if resultado.get("status") != "success":
                            st.sidebar.error(f"El Sheet rechazó los datos: {resultado.get('message')}")
                    except Exception as err_post:
                        st.sidebar.error(f"No se pudo guardar en el Sheet: {err_post}")

                    st.session_state.df_movimientos = pd.concat(
                        [df_actual, df_a_anadir], ignore_index=True
                    )
                    st.sidebar.success(f"¡Se han añadido {len(df_a_anadir)} movimientos nuevos!")
                    st.rerun()
                else:
                    st.sidebar.info("Todos los movimientos del archivo ya estaban registrados.")
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

# 1. Categorías seguras ("Todas" siempre primera, el resto ordenado alfabéticamente)
if not df.empty and "Categoría" in df.columns:
    cats_en_df = df["Categoría"].dropna().unique().tolist()
else:
    cats_en_df = []
otras_categorias = sorted(set(CATEGORIAS_BASE + [str(c) for c in cats_en_df]))
lista_categorias = ["Todas"] + otras_categorias

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

# --- TABLA DE DATOS FILTRADOS (EDITABLE) ---
st.subheader("📋 Registro Completo (Filtrado)")
st.caption("Puedes cambiar la Categoría de cualquier fila directamente en la tabla. Se guardará en el Google Sheet.")

if not df_filtered.empty:
    opciones_categoria = [c for c in lista_categorias if c != "Todas"]
    df_editable = df_filtered[["Fecha", "Concepto", "Categoría", "Importe"]].copy().reset_index(drop=True)

    df_editado = st.data_editor(
        df_editable,
        use_container_width=True,
        hide_index=True,
        disabled=["Fecha", "Concepto", "Importe"],
        column_config={
            "Categoría": st.column_config.SelectboxColumn("Categoría", options=opciones_categoria, required=True),
            "Importe": st.column_config.NumberColumn("Importe", format="%.2f €"),
        },
        key="editor_movimientos",
    )

    filas_cambiadas = df_editado["Categoría"] != df_editable["Categoría"]
    if filas_cambiadas.any():
        cambios = df_editado[filas_cambiadas]
        actualizaciones = [
            {
                "fecha": row["Fecha"],
                "concepto": row["Concepto"],
                "importe": row["Importe"],
                "categoria": row["Categoría"],
            }
            for _, row in cambios.iterrows()
        ]
        try:
            resultado = actualizar_categorias_en_sheet(actualizaciones)
            if resultado.get("status") == "success":
                for cambio in actualizaciones:
                    mask = (
                        (st.session_state.df_movimientos["Fecha"] == cambio["fecha"]) &
                        (st.session_state.df_movimientos["Concepto"] == cambio["concepto"]) &
                        (st.session_state.df_movimientos["Importe"] == cambio["importe"])
                    )
                    st.session_state.df_movimientos.loc[mask, "Categoría"] = cambio["categoria"]
                st.success(f"Categoría actualizada en {resultado.get('actualizadas', len(actualizaciones))} movimiento(s).")
                st.rerun()
            else:
                st.error(f"No se pudo actualizar el Sheet: {resultado.get('message')}")
        except Exception as err:
            st.error(f"Error actualizando categoría: {err}")
else:
    st.warning("No hay movimientos cargados o que coincidan con los filtros seleccionados.")
