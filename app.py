import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Gestión Bancaria", layout="wide")

st.title("💳 Dashboard de Gestión Bancaria y Recibos Futuros")

# --- 1. CARGA DEL ARCHIVO CSV ---
uploaded_file = st.sidebar.file_uploader("Sube el CSV de tu banco", type=["csv"])

if uploaded_file is not None:
    # Cargar datos desde el CSV
    df = pd.read_csv(uploaded_file)
    
    # Estandarizar columnas (Ejemplo básico adaptado a campos comunes)
    # Asumimos que el CSV contiene: Fecha, Concepto, Importe
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    df['Importe'] = df['Importe'].astype(float)
    
    # --- 2. MOTOR DE DETECCIÓN DE RECIBOS RECURRENTES ---
    # Buscamos conceptos de gasto habituales (ej. Luz, Agua, Alquiler)
    conceptos_clave = ["luz", "endesa", "iberdrola", "agua", "alquiler", "comunidad", "netflix"]
    
    gastos_futuros = []
    hoy = datetime.now()
    
    for concepto in conceptos_clave:
        historico = df[df['Concepto'].str.contains(concepto, case=False, na=False)]
        if not historico.empty:
            # Calcular importe medio del recibo
            importe_medio = historico['Importe'].mean()
            # Estimar cobro para el mes actual
            gastos_futuros.append({
                "Concepto": concepto.capitalize(),
                "Importe Estimado": abs(importe_medio),
                "Estado": "Pendiente de cobro"
            })

    df_futuros = pd.DataFrame(gastos_futuros)
    
    # --- 3. CÁLCULO DE SALDOS ---
    saldo_actual = df['Importe'].sum()  # O extraído del último registro del CSV
    compromisos = df_futuros['Importe Estimado'].sum() if not df_futuros.empty else 0
    saldo_disponible = saldo_actual - compromisos

    # --- 4. VISUALIZACIÓN EN DASHBOARD ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Saldo Real Actual", f"{saldo_actual:,.2f} €")
    col2.metric("Recibos Pendientes Estimados", f"-{compromisos:,.2f} €")
    col3.metric("Saldo Libre Real", f"{saldo_disponible:,.2f} €", delta_color="normal")

    st.divider()

    st.subheader("🔮 Próximos Recibos Proyectados este Mes")
    if not df_futuros.empty:
        st.dataframe(df_futuros, use_container_width=True)
    else:
        st.info("No se han detectado recibos recurrentes pendientes en el periodo.")

    st.subheader("📋 Histórico de Movimientos Cargados")
    st.dataframe(df, use_container_width=True)

else:
    st.info("👋 Por favor, sube un archivo CSV en el panel izquierdo para comenzar.")
