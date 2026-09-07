import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Dashboard de Gestión Bancaria", layout="wide", initial_sidebar_state="expanded")

st.title("💳 Dashboard de Gestión Bancaria y Recibos Futuros")

# --- FUNCIÓN DE LECTURA DE ARCHIVOS ---
def cargar_archivo(uploaded_file, skip_rows_manual):
    file_name = uploaded_file.name.lower()
    try:
        uploaded_file.seek(0)
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
            return None, 0

        if skip_rows_manual > 0:
            header_row = skip_rows_manual
        else:
            header_row = 0
            for idx, row in df_temp.iterrows():
                cells = [str(val).strip().lower() for val in row if pd.notna(val)]
                has_fecha = any('fecha' in c for c in cells)
                has_concepto = any(k in c for c in cells for k in ['concepto', 'detalle', 'descripcion', 'descripción'])
                has_importe = any(k in c for c in cells for k in ['importe', 'monto', 'saldo', 'cantidad'])
                
                if has_fecha and has_concepto and has_importe:
                    header_row = idx
                    break

        uploaded_file.seek(0)
        if file_name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8', skiprows=header_row)
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='latin-1', sep=None, engine='python', skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)
            
        df = df.loc[:, ~df.columns.astype(str).str.contains('^Unnamed', na=False)]
        df = df.dropna(how='all')
        
        return df, header_row
        
    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
        return None, 0

# --- SIDEBAR: CARGA DE ARCHIVO ---
st.sidebar.header("📥 Ingesta de Datos")

skip_rows_manual = st.sidebar.number_input(
    "Forzar filas a ignorar (0 = automático):", 
    min_value=0, max_value=30, value=0, step=1
)

uploaded_file = st.sidebar.file_uploader(
    "Sube el extracto bancario (CSV o Excel)", 
    type=["csv", "xlsx", "xls"]
)

if uploaded_file is not None:
    df_raw, header_row_used = cargar_archivo(uploaded_file, skip_rows_manual)
    
    if df_raw is not None and not df_raw.empty:
        st.sidebar.success(f"Archivo cargado ({len(df_raw)} movimientos)")
        
        # --- MAPEO INTELIGENTE DE COLUMNAS ---
        st.sidebar.subheader("⚙️ Mapeo de Columnas")
        columnas = [str(c).strip() for c in df_raw.columns]
        df_raw.columns = columnas
        
        col_fecha_default = next((i for i, c in enumerate(columnas) if 'fecha' in c.lower()), 0)
        col_concepto_default = next((i for i, c in enumerate(columnas) if 'concepto' in c.lower() or 'descrip' in c.lower()), min(1, len(columnas)-1))
        col_importe_default = next((i for i, c in enumerate(columnas) if 'importe' in c.lower() or 'monto' in c.lower()), min(2, len(columnas)-1))
        col_saldo_default = next((i for i, c in enumerate(columnas) if 'saldo' in c.lower()), None)
        
        col_fecha = st.sidebar.selectbox("Columna de Fecha:", columnas, index=col_fecha_default)
        col_concepto = st.sidebar.selectbox("Columna de Concepto:", columnas, index=col_concepto_default)
        col_importe = st.sidebar.selectbox("Columna de Importe (€):", columnas, index=col_importe_default)
        
        opciones_saldo = ["-- No incluir --"] + columnas
        idx_saldo = (opciones_saldo.index(col_saldo_default) if col_saldo_default in opciones_saldo else 0)
        col_saldo = st.sidebar.selectbox("Columna de Saldo (Opcional):", opciones_saldo, index=idx_saldo)
        
        # --- PROCESAMIENTO DE DATOS ---
        df = df_raw.copy()
        
        df['Fecha_Clean'] = pd.to_datetime(df[col_fecha], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['Fecha_Clean']).sort_values('Fecha_Clean', ascending=True) # Ordenar de más antiguo a más reciente
        
        def limpiar_importe(val):
            if pd.isna(val):
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            s = str(val).replace('€', '').replace('EUR', '').replace(' ', '').strip()
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
        
        # --- CÁLCULO DE SALDOS E INICIO DE PERIODO ---
        if col_saldo != "-- No incluir --":
            df['Saldo_Clean'] = df[col_saldo].apply(limpiar_importe)
            saldo_actual = df['Saldo_Clean'].iloc[-1]
            # Saldo previo al primer movimiento del archivo
            saldo_inicial = df['Saldo_Clean'].iloc[0] - df['Importe_Clean'].iloc[0]
        else:
            saldo_actual = df['Importe_Clean'].sum()
            saldo_inicial = 0.0

        # --- MOTOR DE PREDICCIÓN DE RECIBOS RECURRENTES ---
        conceptos_clave = [
            'luz', 'endesa', 'iberdrola', 'naturgy', 'agbar', 'agua', 'gas',
            'alquiler', 'hipoteca', 'comunidad', 'netflix', 'spotify', 'gimnasio',
            'amazon', 'seguro', 'vodafone', 'movistar', 'orange', 'paypal', 'carref', 'bazar'
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
        compromisos = df_futuros['Importe Estimado (€)'].sum() if not df_futuros.empty else 0.0
        saldo_disponible = saldo_actual - compromisos
        
        # --- DASHBOARD PRINCIPAL ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Saldo Inicial Periodo", f"{saldo_inicial:,.2f} €")
        col2.metric("Saldo Actual en Cuenta", f"{saldo_actual:,.2f} €")
        col3.metric("Recibos Pendientes Estimados", f"-{compromisos:,.2f} €")
        col4.metric("Saldo Libre Disponible", f"{saldo_disponible:,.2f} €")
        
        st.divider()
        
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.subheader("🔮 Próximos Recibos Proyectados")
            if not df_futuros.empty:
                st.dataframe(df_futuros, use_container_width=True)
            else:
                st.info("No se han detectado patrones de recibos recurrentes pendientes.")
                
        with col_right:
            st.subheader("📊 Balance del Periodo")
            ingresos = df[df['Importe_Clean'] > 0]['Importe_Clean'].sum()
            gastos = abs(df[df['Importe_Clean'] < 0]['Importe_Clean'].sum())
            
            df_resumen = pd.DataFrame({
                "Concepto": ["Saldo Inicial", "(+) Ingresos Totales", "(-) Gastos Totales", "(=) Saldo Actual"],
                "Monto (€)": [saldo_inicial, ingresos, gastos, saldo_actual]
            })
            st.dataframe(df_resumen, use_container_width=True)
            
        st.divider()
        st.subheader("📋 Movimientos Procesados")
        
        df_display = df.sort_values('Fecha_Clean', ascending=False)[['Fecha_Clean', 'Concepto_Clean', 'Importe_Clean']].copy()
        df_display.columns = ['Fecha', 'Concepto', 'Importe (€)']
        st.dataframe(df_display, use_container_width=True)

else:
    st.info("👋 Por favor, sube un archivo **CSV** o **Excel (.xlsx, .xls)** en el panel de la izquierda para comenzar.")
