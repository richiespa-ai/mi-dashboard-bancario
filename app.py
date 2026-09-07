import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Dashboard de Gestión Bancaria", layout="wide", initial_sidebar_state="expanded")

st.title("💳 Dashboard de Gestión Bancaria y Recibos Futuros")

# --- DETECCIÓN AUTOMÁTICA Y CARGA DE ARCHIVOS ---
def cargar_archivo(uploaded_file):
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
            return None

        # Algoritmo de detección inteligente de cabecera
        header_row = 0
        for idx, row in df_temp.iterrows():
            cells = [str(val).strip().lower() for val in row if pd.notna(val)]
            has_fecha = any('fecha' in c for c in cells)
            has_concepto = any(k in c for k in cells for k in ['concepto', 'detalle', 'descripcion', 'descripción'])
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
        
        return df
        
    except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")
        return None

# --- SIDEBAR: INGESTA Y FILTROS ---
st.sidebar.header("📥 Ingesta de Datos")

uploaded_file = st.sidebar.file_uploader(
    "Sube el extracto bancario (CSV o Excel)", 
    type=["csv", "xlsx", "xls"]
)

if uploaded_file is not None:
    df_raw = cargar_archivo(uploaded_file)
    
    if df_raw is not None and not df_raw.empty:
        st.sidebar.success(f"Archivo cargado correctamente ({len(df_raw)} movimientos)")
        
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
        col_saldo = st.sidebar.selectbox("Columna de Saldo:", opciones_saldo, index=idx_saldo)
        
        # Filtro por texto
        st.sidebar.subheader("🔍 Filtro de Movimientos")
        search_query = st.sidebar.text_input("Buscar por palabra clave:", "")

        # --- PROCESAMIENTO Y LIMPIEZA DE DATOS ---
        df = df_raw.copy()
        
        df['Fecha_Clean'] = pd.to_datetime(df[col_fecha], errors='coerce', dayfirst=True)
        df = df.dropna(subset=['Fecha_Clean']).sort_values('Fecha_Clean', ascending=True)
        
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
        
        # Categorización automática
        def categorizar(concepto):
            c = concepto.lower()
            if any(k in c for k in ['carref', 'alimen', 'farma', 'super', 'mercadona', 'lidl', 'dia', 'eroski', 'bazar']):
                return 'Supermercados y Compras'
            elif any(k in c for k in ['iberdrola', 'endesa', 'naturgy', 'agua', 'agbar', 'gas', 'luz', 'vodafone', 'orange', 'movistar']):
                return 'Suministros y Hogar'
            elif any(k in c for k in ['parfois', 'mago', 'adela gil', 'amazon', 'zara', 'pago 3 plazos', 'paypal', 'c&a']):
                return 'Ocio y Tiendas'
            elif any(k in c for k in ['tribut', 'impuest', 'seguro', 'comunidad', 'hipoteca', 'alquiler']):
                return 'Impuestos y Recibos'
            elif any(k in c for k in ['bizum', 'transf', 'remun']):
                return 'Transferencias / Bizum'
            else:
                return 'Otros Movimientos'

        df['Categoria'] = df['Concepto_Clean'].apply(categorizar)
        
        # --- CÁLCULO DE SALDOS ---
        if col_saldo != "-- No incluir --":
            df['Saldo_Clean'] = df[col_saldo].apply(limpiar_importe)
            saldo_actual = df['Saldo_Clean'].iloc[-1]
            saldo_inicial = df['Saldo_Clean'].iloc[0] - df['Importe_Clean'].iloc[0]
        else:
            saldo_actual = df['Importe_Clean'].sum()
            saldo_inicial = 0.0

        # --- MOTOR DE PREDICCIÓN DE RECIBOS ---
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
                        "Día Estimado": f"Día {dia_estimado}"
                    })

        df_futuros = pd.DataFrame(gastos_futuros)
        compromisos = df_futuros['Importe Estimado (€)'].sum() if not df_futuros.empty else 0.0
        saldo_disponible = saldo_actual - compromisos
        
        # --- DASHBOARD PRINCIPAL: MÉTRICAS ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Saldo Inicial Periodo", f"{saldo_inicial:,.2f} €")
        col2.metric("Saldo Actual en Cuenta", f"{saldo_actual:,.2f} €")
        col3.metric("Recibos Pendientes Estimados", f"-{compromisos:,.2f} €")
        col4.metric("Saldo Libre Disponible", f"{saldo_disponible:,.2f} €")
        
        st.divider()
        
        # --- FILA DE GRÁFICOS Y ANÁLISIS ---
        col_g1, col_g2 = st.columns([1, 1])
        
        with col_g1:
            st.subheader("📊 Ingresos vs. Gastos")
            ingresos = df[df['Importe_Clean'] > 0]['Importe_Clean'].sum()
            gastos = abs(df[df['Importe_Clean'] < 0]['Importe_Clean'].sum())
            
            fig_bar = go.Figure(data=[
                go.Bar(
                    x=["Ingresos Totales", "Gastos Totales"],
                    y=[ingresos, gastos],
                    marker_color=['#81c784', '#e57373'],
                    text=[f"{ingresos:,.2f} €", f"{gastos:,.2f} €"],
                    textposition='auto',
                )
            ])
            fig_bar.update_layout(
                yaxis_title="Euros (€)",
                height=300,
                margin=dict(l=20, r=20, t=20, b=20),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_g2:
            st.subheader("🍩 Distribución de Gastos por Categoria")
            df_gastos_cat = df[df['Importe_Clean'] < 0].groupby('Categoria')['Importe_Clean'].sum().abs().reset_index()
            if not df_gastos_cat.empty:
                fig_pie = px.pie(
                    df_gastos_cat, 
                    values='Importe_Clean', 
                    names='Categoria', 
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_pie.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No hay gastos registrados en el periodo.")

        st.divider()

        # --- SEGUNDA FILA DE ANÁLISIS ---
        col_l1, col_l2 = st.columns([1, 1])

        with col_l1:
            st.subheader("📈 Evolución Diaria del Saldo")
            if col_saldo != "-- No incluir --":
                fig_line = px.line(
                    df, 
                    x='Fecha_Clean', 
                    y='Saldo_Clean',
                    labels={'Fecha_Clean': 'Fecha', 'Saldo_Clean': 'Saldo (€)'},
                    line_shape='linear'
                )
                fig_line.update_traces(line_color='#29b6f6', line_width=3)
                fig_line.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.info("Selecciona la columna de Saldo para visualizar la línea temporal.")

        with col_l2:
            st.subheader("🔮 Próximos Recibos Proyectados")
            if not df_futuros.empty:
                st.dataframe(df_futuros, use_container_width=True, height=250)
            else:
                st.info("No se detectaron patrones de recibos recurrentes.")

        st.divider()

        # --- SECCIÓN DE MAYORES GASTOS ---
        st.subheader("🔝 Top 5 Mayores Gastos del Periodo")
        top_gastos = df[df['Importe_Clean'] < 0].sort_values('Importe_Clean', ascending=True).head(5)
        
        cols_top = st.columns(len(top_gastos))
        for i, (_, row) in enumerate(top_gastos.iterrows()):
            with cols_top[i]:
                st.caption(row['Fecha_Clean'].strftime('%Y-%m-%d'))
                st.metric(label=row['Concepto_Clean'][:18], value=f"{row['Importe_Clean']:,.2f} €")

        st.divider()

        # --- TABLA INTERACTIVA DE MOVIMIENTOS ---
        st.subheader("📋 Movimientos Procesados")
        
        # Aplicar filtro por palabra clave
        df_filtered = df.copy()
        if search_query:
            df_filtered = df_filtered[df_filtered['Concepto_Clean'].str.contains(search_query, case=False, na=False)]
        
        df_display = df_filtered.sort_values('Fecha_Clean', ascending=False)[['Fecha_Clean', 'Concepto_Clean', 'Categoria', 'Importe_Clean']].copy()
        df_display['Fecha_Clean'] = df_display['Fecha_Clean'].dt.strftime('%Y-%m-%d')
        df_display.columns = ['Fecha', 'Concepto', 'Categoría', 'Importe (€)']
        
        # Formato de color (Verde clarito / Rojo clarito)
        def color_importe(val):
            if val < 0:
                return 'background-color: #ffcdd2; color: #b71c1c; font-weight: bold;'
            elif val > 0:
                return 'background-color: #c8e6c9; color: #1b5e20; font-weight: bold;'
            return ''

        st.dataframe(
            df_display.style.applymap(color_importe, subset=['Importe (€)']).format({'Importe (€)': '{:,.2f} €'}),
            use_container_width=True,
            height=400
        )

else:
    st.info("👋 Por favor, sube un archivo **CSV** o **Excel (.xlsx, .xls)** en el panel de la izquierda para comenzar.")
