import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Dashboard de Gestión Bancaria", layout="wide", initial_sidebar_state="expanded")

st.title("💳 Dashboard de Gestión Bancaria y Recibos Futuros")

# --- FUNCION DE LECTURA DE ARCHIVOS CON BUSQUEDA DE ENCABEZADOS ---
def cargar_archivo(uploaded_file):
    file_name = uploaded_file.name.lower()
    try:
        if file_name.endswith('.csv'):
            try:
                df_temp = pd.read_csv(uploaded_file, encoding='utf-8', header=None)
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df_temp = pd.read_csv(uploaded_file, encoding='latin-1', sep=None, engine='python', header=None)
        elif file_name.endswith(('.xlsx', '.xls')):
            df_temp = pd.read_excel(uploaded_file, header=None)
        else:
            st.error("Formato no soportado.")
            return None

        # Buscar la fila donde aparecen palabras clave de banco
        header_row = 0
        keywords = ['fecha', 'concepto', 'importe', 'movimiento', 'saldo', 'operacion']
        
        for idx, row in df_temp.iterrows():
            row_str = " ".join(row.astype(str)).lower()
            if any(kw in row_str for kw in keywords):
                header_row = idx
                break
        
        # Recargar los datos asignando correctamente la cabecera encontrada
        uploaded_file.seek(0)
        if file_name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8', skiprows=header_row)
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='latin-1', sep=None, engine='python', skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)
            
        # Limpiar columnas vacías de relleno (unnamed)
        df = df.loc[:, ~df.columns.str.contains('^Unnamed', na=False)]
        df = df.dropna(how='all')
        
        return df
        
    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
        return None

# --- SIDEBAR: CARGA DE ARCHIVO ---
st.sidebar.header("📥 Ingesta de Datos")
uploaded_file = st.sidebar.file_uploader(
    "Sube el extracto bancario (CSV o Excel)", 
    type=["csv", "xlsx", "xls"],
    help="Admite archivos exportados desde la banca online."
)

if uploaded_file is not None:
    df_raw = cargar_archivo(uploaded_file)
    
    if df_raw is not None and not df_raw.empty:
        st.sidebar.success(f"Archivo cargado: **{uploaded_file.name}** ({len(df_raw)} movimientos)")
        
        # --- MAPEO INTELIGENTE DE COLUMNAS ---
        st.sidebar.subheader("⚙️ Mapeo de Columnas")
        columnas = list(df_raw.columns)
        
        col_fecha_default = next((i for i, c in enumerate(columnas) if any(k in str(c).lower() for k in ['fecha', 'date', 'f.oper'])), 0)
        col_concepto_default = next((i for i, c in enumerate(columnas) if any(k in str(c).lower() for k in ['concepto', 'descrip', 'detalle', 'movimiento'])), min(1, len(columnas)-1))
        col_importe_default = next((i for i, c in enumerate(columnas) if any(k in str(c).lower() for k in ['importe', 'cantidad', 'monto'])), min(2, len(columnas)-1))
        col_saldo_default = next((i for i, c in enumerate(columnas) if any(k in str(c).lower() for k in ['saldo', 'balance'])), None)
        
        col_fecha = st.sidebar.selectbox("Columna de Fecha:", columnas, index=col_fecha_default)
        col_concepto = st.sidebar.selectbox("Columna de Concepto:", columnas, index=col_concepto_default)
        col_importe = st.sidebar.selectbox("Columna de Importe (€):", columnas, index=col_importe_default)
        
        opciones_saldo = ["-- No incluir --"] + columnas
        idx_saldo = (opciones_saldo.index(col_saldo_default) if col_saldo_default in opciones_saldo else 0)
        col_saldo = st.sidebar.selectbox("Columna de Saldo (Opcional):", opciones_saldo, index=idx_saldo)
        
        # --- PROCESAMIENTO DE DATOS ---
        df = df_raw.copy()
        
        df['Fecha_Clean'] = pd.to_datetime(df[col_fecha], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['Fecha_Clean']).sort_values('Fecha_Clean', ascending=False)
        
        def limpiar_importe(val):
            if pd.isna(val):
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            s = str(val).replace('€', '').replace(' ', '').strip()
            if ',' in s and '.' in s:
                if s.rfind(',') > s.rfind('.'):
                    s = s.replace('.', '').replace(',', '.')
                else:
                    s = s.replace(',', '')
            elif ',' in s:
                s = s.replace(',', '.')
            try:
                return float(s)
            except:
                return 0.0

        df['Importe_Clean'] = df[col_importe].apply(limpiar_importe)
        df['Concepto_Clean'] = df[col_concepto].astype(str).str.strip()
        
        # --- MOTOR DE PREDICCIÓN DE RECIBOS ---
        conceptos_clave = [
            'luz', 'endesa', 'iberdrola', 'naturgy', 'agbar', 'agua', 'gas',
            'alquiler', 'hipoteca', 'comunidad', 'netflix', 'spotify', 'gimnasio',
            'amazon', 'seguro', 'vodafone', 'movistar', 'orange', 'paypal', 'carref'
        ]
        
        gastos_futuros = []
        for kw in conceptos_clave:
            matches = df[df['Concepto_Clean'].str.contains(kw, case=False, na=False)]
            if not matches.empty:
                gastos_negativos = matches[matches['Importe_Clean'] < 0]
                if not gastos_negativos.empty:
                    importe_medio = abs(gastos_negativos['Importe_Clean'].mean())
                    ultimo_pago = gastos_negativos['Fecha_Clean'].max()
                    dias = gastos_negativos['Fecha_Clean'].dt.day
                    dia_estimado = int(dias.median())
                    
                    gastos_futuros.append({
                        "Concepto": kw.capitalize(),
                        "Importe Estimado (€)": round(importe_medio, 2),
                        "Último Pago": ultimo_pago.strftime('%Y-%m-%d'),
                        "Día Estimado del Mes": f"Día {dia_estimado}"
                    })

        df_futuros = pd.DataFrame(gastos_futuros)
        
        # --- CÁLCULO DE MÉTRICAS ---
        if col_saldo != "-- No incluir --":
            df['Saldo_Clean'] = df[col_saldo].apply(limpiar_importe)
            saldo_actual = df['Saldo_Clean'].iloc[0]
        else:
            saldo_actual = df['Importe_Clean'].sum()
            
        compromisos = df_futuros['Importe Estimado (€)'].sum() if not df_futuros.empty else 0.0
        saldo_disponible = saldo_actual - compromisos
        
        # --- DASHBOARD ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Saldo Real Actual", f"{saldo_actual:,.2f} €")
        col2.metric("Recibos Pendientes Estimados", f"-{compromisos:,.2f} €")
        col3.metric("Saldo Libre Real", f"{saldo_disponible:,.2f} €")
        
        st.divider()
        
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.subheader("🔮 Próximos Recibos Proyectados este Mes")
            if not df_futuros.empty:
                st.dataframe(df_futuros, use_container_width=True)
            else:
                st.info("No se han detectado patrones de recibos recurrentes pendientes.")
                
        with col_right:
            st.subheader("📊 Resumen del Periodo")
            ingresos = df[df['Importe_Clean'] > 0]['Importe_Clean'].sum()
            gastos = abs(df[df['Importe_Clean'] < 0]['Importe_Clean'].sum())
            
            df_resumen = pd.DataFrame({
                "Tipo": ["Ingresos Totales", "Gastos Totales"],
                "Monto (€)": [ingresos, gastos]
            })
            st.dataframe(df_resumen, use_container_width=True)
            
        st.divider()
        st.subheader("📋 Movimientos Procesados")
        
        df_display = df[['Fecha_Clean', 'Concepto_Clean', 'Importe_Clean']].copy()
        df_display.columns = ['Fecha', 'Concepto', 'Importe (€)']
        st.dataframe(df_display, use_container_width=True)

else:
    st.info("👋 Por favor, sube un archivo **CSV** o **Excel (.xlsx, .xls)** en el panel de la izquierda para comenzar.")
