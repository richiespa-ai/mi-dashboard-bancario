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

# URL de la base de datos en Google Sheets (sin #gid=0 para evitar HTTP 400)
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1tfnhAs8VeaciHXWJ4J0UDxkhvOiuR-_FvDRnHD0tqxI/edit"

@st.cache_data(ttl=60)
def load_all_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 1. Cargar pestaña 'Movimientos'
    try:
        df_mov = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Movimientos", ttl="1m")
    except Exception:
        df_mov = conn.read(spreadsheet=SPREADSHEET_URL, ttl="1m")

    # Asegurar estructura de columnas si la pestaña está vacía
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

    # 2. Cargar pestaña 'Categorías'
    try:
        df_cat = conn.read(spreadsheet=SPREADSHEET_URL, worksheet="Categorías", ttl="1m")
    except Exception:
        df_cat = pd.DataFrame({
            "Categoría Principal": ["Ingresos Operativos", "Gastos de Personal", "Gastos Operativos", "Gastos Financieros", "Impuestos y Tasas"],
            "Subcategoría": ["Ventas Clientes", "Nóminas", "Alquileres", "Comisiones Bancarias", "IVA / Sociedades"],
            "Tipo": ["Ingreso", "Gasto", "Gasto", "Gasto", "Gasto"]
        })

    return df_mov, df_cat

try:
    df, df_cat = load_all_data()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# --- SIDEBAR: IMPORTACIÓN DE ARCHIVOS EXCEL / CSV ---
st.sidebar.header("📁 Importar Extracto Bancario")

uploaded_file = st.sidebar.file_uploader("Subir extracto (Excel o CSV)", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    banco_origen = st.sidebar.selectbox("Cuenta / Banco de destino", ["BBVA Principal", "CaixaBank", "Otro"])
    
    if st.sidebar.button("Procesar y Volcar a Google Sheets"):
        try:
            if uploaded_file.name.endswith(".csv"):
                df_excel = pd.read_csv(uploaded_file)
            else:
                df_excel = pd.read_excel(uploaded_file)
            
            nuevos_registros = []
            start_id = len(df) + 1
            
            for idx, row in df_excel.iterrows():
                # Búsqueda flexible de columnas según formato común de extracto
                fecha_val = row.get("Fecha") or row.get("Fecha Valor") or row.get("F.Operación") or row.get("FECHA")
                concepto_val = row.get("Concepto") or row.get("Descripción") or row.get("Leyenda") or row.get("CONCEPTO") or "Movimiento Importado"
                importe_val = row.get("Importe") or row.get("Monto") or row.get("IMPORTE") or 0.0
                
                try:
                    importe_float = float(str(importe_val).replace(".", "").replace(",", ".")) if isinstance(importe_val, str) else float(importe_val)
                except ValueError:
                    importe_float = 0.0
                
                tipo_val = "Ingreso" if importe_float >= 0 else "Gasto"
                
                fecha_str = str(pd.to_datetime(fecha_val, errors='coerce').date()) if pd.notnull(fecha_val) else str(pd.Timestamp.now().date())
                
                nuevos_registros.append({
                    "ID_Movimiento": f"MOV-{start_id + idx:04d}",
                    "Fecha": fecha_str,
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
            
            # Combinar manteniendo formato de fechas
            if df.empty:
                df_actualizado = df_nuevos
            else:
                df_copy = df.copy()
                df_copy['Fecha'] = df_copy['Fecha'].dt.strftime('%Y-%m-%d')
                df_actualizado = pd.concat([df_copy, df_nuevos], ignore_index=True)
            
            # Volcar a Google Sheets
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Movimientos", data=df_actualizado)
            
            st.sidebar.success(f"¡{len(df_nuevos)} movimientos importados con éxito!")
            st.cache_data.clear()
            st.rerun()
            
        except Exception as err:
            st.sidebar.error(f"Error al procesar el archivo: {err}")

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

# --- TABLA DE DATOS ---
st.subheader("📋 Registro de Movimientos Bancarios (`Movimientos`)")
if not df_filtered.empty:
    df_mostrar = df_filtered.copy()
    df_mostrar['Fecha'] = df_mostrar['Fecha'].dt.strftime('%Y-%m-%d')
    st.dataframe(
        df_mostrar.style.format({"Importe": "{:,.2f} €"}),
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("No hay movimientos registrados. Sube un extracto bancario en el menú lateral o añade uno manualmente.")

# --- FORMULARIO DE REGISTRO MANUAL ---
with st.expander("➕ Añadir movimiento manualmente"):
    lista_cats = df_cat["Categoría Principal"].dropna().unique().tolist() if not df_cat.empty else ["Sin Categorizar"]
    
    with st.form("manual_entry"):
        c1, c2, c3 = st.columns(3)
        with c1:
            fecha_in = st.date_input("Fecha")
            cuenta_in = st.selectbox("Cuenta / Banco", ["BBVA Principal", "CaixaBank", "Otro"])
            concepto_in = st.text_input("Concepto / Descripción")
        with c2:
            tipo_in = st.selectbox("Tipo", ["Gasto", "Ingreso"])
            cat_in = st.selectbox("Categoría", lista_cats)
            subcat_in = st.text_input("Subcategoría")
        with c3:
            importe_in = st.number_input("Importe (€)", value=0.0, step=10.0)
            estado_in = st.selectbox("Estado", ["Pendiente", "Conciliado"])
            notas_in = st.text_input("Notas / Observaciones")

        submitted = st.form_submit_button("Guardar Movimiento")

        if submitted:
            val_imp = abs(importe_in) if tipo_in == "Ingreso" else -abs(importe_in)
            new_id = f"MOV-{len(df) + 1:04d}"
            
            df_nuevo = pd.DataFrame([{
                "ID_Movimiento": new_id,
                "Fecha": str(fecha_in),
                "Cuenta / Banco": cuenta_in,
                "Concepto / Descripción": concepto_in,
                "Tipo": tipo_in,
                "Categoría": cat_in,
                "Subcategoría": subcat_in,
                "Importe": val_imp,
                "Estado": estado_in,
                "Notas / Observaciones": notas_in
            }])
            
            if df.empty:
                df_guardar = df_nuevo
            else:
                df_copy = df.copy()
                df_copy['Fecha'] = df_copy['Fecha'].dt.strftime('%Y-%m-%d')
                df_guardar = pd.concat([df_copy, df_nuevo], ignore_index=True)
                
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(spreadsheet=SPREADSHEET_URL, worksheet="Movimientos", data=df_guardar)
            st.success("Movimiento guardado en Google Sheets")
            st.cache_data.clear()
            st.rerun()
