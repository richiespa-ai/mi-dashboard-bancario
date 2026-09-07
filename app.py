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

# ID de la nueva base de datos Google Sheet
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1tfnhAs8VeaciHXWJ4J0UDxkhvOiuR-_FvDRnHD0tqxI/edit#gid=0"

@st.cache_data(ttl=60)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=SPREADSHEET_URL, ttl="1m")
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    df['Importe'] = pd.to_numeric(df['Importe'])
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"Error al conectar con la base de datos de Google Sheets: {e}")
    st.stop()

# --- SIDEBAR DE FILTROS ---
st.sidebar.header("🔍 Filtros")

bancos = ["Todos"] + sorted(list(df["Cuenta / Banco"].dropna().unique()))
banco_sel = st.sidebar.selectbox("Cuenta / Banco", bancos)

tipos = ["Todos"] + sorted(list(df["Tipo"].dropna().unique()))
tipo_sel = st.sidebar.selectbox("Tipo de Movimiento", tipos)

categorias = ["Todas"] + sorted(list(df["Categoría"].dropna().unique()))
cat_sel = st.sidebar.selectbox("Categoría", categorias)

estados = ["Todos"] + sorted(list(df["Estado"].dropna().unique()))
estado_sel = st.sidebar.selectbox("Estado", estados)

# Aplicar filtros
df_filtered = df.copy()

if banco_sel != "Todos":
    df_filtered = df_filtered[df_filtered["Cuenta / Banco"] == banco_sel]
if tipo_sel != "Todos":
    df_filtered = df_filtered[df_filtered["Tipo"] == tipo_sel]
if cat_sel != "Todas":
    df_filtered = df_filtered[df_filtered["Categoría"] == cat_sel]
if estado_sel != "Todos":
    df_filtered = df_filtered[df_filtered["Estado"] == estado_sel]

# --- MÉTRICAS PRINCIPALES (KPIS) ---
ingresos = df_filtered[df_filtered["Importe"] > 0]["Importe"].sum()
gastos = df_filtered[df_filtered["Importe"] < 0]["Importe"].sum()
balance = ingresos + gastos

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ingresos Totales", f"{ingresos:,.2f} €")
col2.metric("Gastos Totales", f"{abs(gastos):,.2f} €")
col3.metric("Balance Neto", f"{balance:,.2f} €")
col4.metric("Nº Transacciones", len(df_filtered))

st.markdown("---")

# --- GRÁFICOS Y ANÁLISIS ---
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.subheader("📊 Distribución de Gastos por Categoría")
    df_gastos = df_filtered[df_filtered["Importe"] < 0].copy()
    if not df_gastos.empty:
        df_gastos["Importe_Abs"] = df_gastos["Importe"].abs()
        fig_cat = px.pie(
            df_gastos,
            values="Importe_Abs",
            names="Categoría",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("No hay datos de gastos registrados con los filtros seleccionados.")

with col_chart2:
    st.subheader("📈 Histórico de Movimientos")
    df_trend = df_filtered.sort_values("Fecha")
    if not df_trend.empty:
        fig_line = px.bar(
            df_trend,
            x="Fecha",
            y="Importe",
            color="Tipo",
            barmode="relative",
            color_discrete_map={"Ingreso": "#2ecc71", "Gasto": "#e74c3c"}
        )
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No hay datos para mostrar en la gráfica.")

# --- TABLA DE DATOS ---
st.subheader("📋 Registro de Movimientos Bancarios")
st.dataframe(
    df_filtered.style.format({"Importe": "{:,.2f} €"}),
    use_container_width=True,
    hide_index=True
)

# --- FORMULARIO PARA AÑADIR REGISTROS ---
with st.expander("➕ Registrar nuevo movimiento"):
    with st.form("nuevo_movimiento"):
        c1, c2, c3 = st.columns(3)
        
        with c1:
            fecha_input = st.date_input("Fecha")
            cuenta_input = st.selectbox("Cuenta / Banco", ["BBVA Principal", "CaixaBank"])
            concepto_input = st.text_input("Concepto / Descripción")
        
        with c2:
            tipo_input = st.selectbox("Tipo", ["Ingreso", "Gasto"])
            categoria_input = st.selectbox(
                "Categoría",
                ["Ingresos Operativos", "Gastos de Personal", "Gastos Operativos", "Gastos Financieros", "Impuestos y Tasas"]
            )
            subcategoria_input = st.text_input("Subcategoría")
        
        with c3:
            importe_input = st.number_input("Importe (€)", value=0.0, step=10.0)
            estado_input = st.selectbox("Estado", ["Conciliado", "Pendiente"])
            notas_input = st.text_area("Notas / Observaciones")

        submitted = st.form_submit_button("Guardar en Google Sheets")

        if submitted:
            conn = st.connection("gsheets", type=GSheetsConnection)
            
            val_importe = abs(importe_input) if tipo_input == "Ingreso" else -abs(importe_input)
            new_id = f"MOV-{len(df) + 1:04d}"
            
            new_data = pd.DataFrame([{
                "ID_Movimiento": new_id,
                "Fecha": str(fecha_input),
                "Cuenta / Banco": cuenta_input,
                "Concepto / Descripción": concepto_input,
                "Tipo": tipo_input,
                "Categoría": categoria_input,
                "Subcategoría": subcategoria_input,
                "Importe": val_importe,
                "Estado": estado_input,
                "Notas / Observaciones": notas_input
            }])
            
            updated_df = pd.concat([df, new_data], ignore_index=True)
            conn.update(spreadsheet=SPREADSHEET_URL, data=updated_df)
            st.success("¡Movimiento añadido exitosamente!")
            st.cache_data.clear()
            st.rerun()
