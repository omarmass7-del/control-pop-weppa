import os
import sqlite3
import pandas as pd
import streamlit as st
import google.generativeai as genai

# ==========================================
# 0. CONFIGURACIÓN DE ACCESO CORPORATIVO Y PÚBLICO
# ==========================================
USUARIOS_AUTORIZADOS = {
    "adm": "weppa2026",
    "angela@weppa.io": "angela2026",
    "omar@weppa.io": "omar2026",
    "maribel@weppa.io": "maribel2026"
}

st.set_page_config(page_title="Control POP Weppa", page_icon="📦", layout="wide")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# ==========================================
# 1. BASE DE DATOS LOCAL (SQLite)
# ==========================================
DB_PATH = "inventario_weppa.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto TEXT UNIQUE NOT NULL,
                categoria TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                ubicacion TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto TEXT NOT NULL,
                tipo_movimiento TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                usuario TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Tabla para las solicitudes de formularios externos
        conn.execute("""
            CREATE TABLE IF NOT EXISTS solicitudes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitante TEXT NOT NULL,
                correo TEXT NOT NULL,
                material TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                estatus TEXT NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

init_db()

# ==========================================
# 2. PANTALLA DE LOGIN O FORMULARIO PÚBLICO
# ==========================================
modo_vista = st.sidebar.radio("Navegación", ["🔐 Iniciar Sesión (Equipo)", "📋 Solicitar Material POP (Externo)"])

if modo_vista == "📋 Solicitar Material POP (Externo)":
    st.title("📋 Formulario de Solicitud de Material POP — Weppa")
    st.markdown("Completa los datos para solicitar material. Una vez enviado, nuestro equipo procesará tu requerimiento.")
    
    with st.form("form_solicitud_externa"):
        nombre_solicitante = st.text_input("Nombre y Apellido").strip()
        correo_solicitante = st.text_input("Correo Electrónico").strip()
        material_solicitado = st.text_input("Material POP / Descripción requerida").strip()
        cantidad_solicitada = st.number_input("Cantidad", min_value=1, step=1)
        
        enviar_form = st.form_submit_button("Enviar Solicitud")
        if enviar_form:
            if nombre_solicitante and correo_solicitante and material_solicitado:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute(
                        "INSERT INTO solicitudes (solicitante, correo, material, cantidad, estatus) VALUES (?, ?, ?, ?, ?)",
                        (nombre_solicitante, correo_solicitante, material_solicitado, cantidad_solicitada, "Recibido")
                    )
                    conn.commit()
                st.success("¡Solicitud enviada con éxito! Tu estatus actual es: **Recibido**. Nos pondremos en contacto pronto.")
            else:
                st.warning("Por favor completa todos los campos obligatorios.")
    st.stop()

# Si no está autenticado para el panel interno
if not st.session_state.autenticado:
    st.title("🔒 Acceso Corporativo — Control POP Weppa")
    st.markdown("Inicia sesión utilizando tu **correo corporativo** (`@weppa.io`) o usuario `adm`.")
    
    with st.form("login_form"):
        usuario = st.text_input("Correo o Usuario").strip().lower()
        clave = st.text_input("Contraseña", type="password")
        entrar = st.form_submit_button("Ingresar al Sistema")
        
        if entrar:
            if usuario in USUARIOS_AUTORIZADOS and USUARIOS_AUTORIZADOS[usuario] == clave:
                st.session_state.autenticado = True
                st.session_state.usuario_actual = usuario
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas. Verifica tu usuario y contraseña.")
    st.stop()

# ==========================================
# 3. FUNCIONES DE GESTIÓN INTERNA
# ==========================================
def obtener_inventario():
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT id, producto AS 'Material', categoria AS 'Categoría', cantidad AS 'Cantidad', ubicacion AS 'Ubicación' FROM inventario", conn)
    return df

def obtener_solicitudes():
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT id, solicitante AS 'Solicitante', correo AS 'Correo', material AS 'Material', cantidad AS 'Cantidad', estatus AS 'Estatus', fecha AS 'Fecha' FROM solicitudes ORDER BY id DESC", conn)
    return df

def actualizar_estatus_solicitud(sol_id, nuevo_estatus):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE solicitudes SET estatus = ? WHERE id = ?", (nuevo_estatus, sol_id))
        conn.commit()

def registrar_movimiento(producto, categoria, cantidad, tipo, ubicacion):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cantidad FROM inventario WHERE producto = ?", (producto,))
        res = cursor.fetchone()
        
        if res is None:
            if tipo == "Entrada":
                cursor.execute("INSERT INTO inventario (producto, categoria, cantidad, ubicacion) VALUES (?, ?, ?, ?)",
                               (producto, categoria, cantidad, ubicacion))
            else:
                return False, "El producto no existe en inventario."
        else:
            nueva_cant = res[0] + cantidad if tipo == "Entrada" else res[0] - cantidad
            if nueva_cant < 0:
                return False, f"Stock insuficiente. Disponible: {res[0]}."
            cursor.execute("UPDATE inventario SET cantidad = ?, ubicacion = ? WHERE producto = ?", (nueva_cant, ubicacion, producto))
        
        cursor.execute("INSERT INTO historial (producto, tipo_movimiento, cantidad, usuario) VALUES (?, ?, ?, ?)", 
                       (producto, tipo, cantidad, st.session_state.usuario_actual))
        conn.commit()
    return True, f"¡{tipo} de {cantidad} unidad(es) de '{producto}' registrada por {st.session_state.usuario_actual}!"

def cargar_masivo(df_subido, modo):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        if modo == "Reemplazar todo el inventario":
            cursor.execute("DELETE FROM inventario")
        
        for _, row in df_subido.iterrows():
            prod = str(row["Material"]).strip()
            cat = str(row.get("Categoría", "General")).strip()
            cant = int(row["Cantidad"])
            ubi = str(row.get("Ubicación", "Almacén Principal")).strip()
            
            cursor.execute("SELECT cantidad FROM inventario WHERE producto = ?", (prod,))
            existe = cursor.fetchone()
            if existe and modo == "Sumar al inventario actual":
                cursor.execute("UPDATE inventario SET cantidad = ? WHERE producto = ?", (existe[0] + cant, prod))
            else:
                cursor.execute("INSERT OR REPLACE INTO inventario (producto, categoria, cantidad, ubicacion) VALUES (?, ?, ?, ?)",
                               (prod, cat, cant, ubi))
        conn.commit()

# ==========================================
# 4. INTERFAZ DE ADMINISTRACIÓN / EQUIPO
# ==========================================
with st.sidebar:
    st.write(f"👤 Conectado como:\n**{st.session_state.usuario_actual}**")
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

st.title("📦 Control de Material POP — Weppa (Panel Interno)")

tabs = st.tabs([
    "📊 Inventario Actual", 
    "📥 Solicitudes Externas",
    "➕ Registro Individual", 
    "📂 Cargar / Descargar Excel", 
    "🤖 Asistente IA Weppa"
])

with tabs[0]:
    df = obtener_inventario()
    if not df.empty:
        col1, col2 = st.columns(2)
        col1.metric("Variedad de Materiales", len(df))
        col2.metric("Total Unidades Disponibles", int(df['Cantidad'].sum()))
        st.dataframe(df, use_container_width=True)
    else:
        st.info("El inventario está vacío. Sube un archivo Excel/CSV o registra materiales.")

with tabs[1]:
    st.subheader("📥 Gestión de Solicitudes Recibidas")
    st.markdown("Aquí puedes revisar las solicitudes que envían los usuarios externos y actualizar su estatus.")
    
    df_sol = obtener_solicitudes()
    if not df_sol.empty:
        for index, row in df_sol.iterrows():
            with st.expander(f"Solicitud #{row['id']} — {row['Solicitante']} ({row['Material']})"):
                st.write(f"📧 **Correo:** {row['Correo']}")
                st.write(f"📦 **Material:** {row['Material']} (Cantidad: {row['Cantidad']})")
                st.write(f"📅 **Fecha:** {row['Fecha']}")
                st.write(f"📌 **Estatus Actual:** `{row['Estatus']}`")
                
                nuevo_estatus = st.selectbox(
                    "Cambiar estatus", 
                    ["Recibido", "En espera pendiente", "Enviado"], 
                    index=["Recibido", "En espera pendiente", "Enviado"].index(row['Estatus']) if row['Estatus'] in ["Recibido", "En espera pendiente", "Enviado"] else 0,
                    key=f"estatus_{row['id']}"
                )
                
                if st.button(f"Actualizar Estatus #{row['id']}", key=f"btn_{row['id']}"):
                    actualizar_estatus_solicitud(row['id'], nuevo_estatus)
                    st.success(f"¡Estatus actualizado a '{nuevo_estatus}' con éxito!")
                    st.rerun()
    else:
        st.info("No hay solicitudes externas registradas todavía.")

with tabs[2]:
    st.subheader("Registrar Entrada o Salida")
    with st.form("form_pop"):
        col_a, col_b = st.columns(2)
        with col_a:
            producto = st.text_input("Nombre del Material", placeholder="Ej: Franelas, Pop-sockets").strip()
            categoria = st.selectbox("Categoría", ["Textil", "Papelería", "Accesorios", "Eventos", "Merchandising"])
            cantidad = st.number_input("Cantidad", min_value=1, step=1)
        with col_b:
            tipo = st.radio("Tipo de Operación", ["Entrada", "Salida"])
            ubicacion = st.text_input("Ubicación / Destino", value="Almacén Principal")
        
        if st.form_submit_button("Guardar Movimiento"):
            if producto:
                ok, msg = registrar_movimiento(producto, categoria, cantidad, tipo, ubicacion)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
            else:
                st.warning("Debes escribir el nombre del material.")

with tabs[3]:
    st.subheader("Importar o Exportar Inventario Masivo")
    df_export = obtener_inventario()
    if df_export.empty:
        df_export = pd.DataFrame({
            "Material": ["Franelas Weppa", "Stickers Promocionales"],
            "Categoría": ["Textil", "Papelería"],
            "Cantidad": [50, 200],
            "Ubicación": ["Caracas", "Lechería"]
        })
    
    st.download_button(
        label="⬇️ Descargar Inventario / Plantilla (CSV)",
        data=df_export.to_csv(index=False).encode('utf-8'),
        file_name="inventario_weppa.csv",
        mime="text/csv"
    )
    st.divider()
    archivo = st.file_uploader("Sube tu archivo de inventario (.xlsx o .csv)", type=["xlsx", "csv"])
    modo_carga = st.radio("¿Qué hacer con los datos subidos?", ["Sumar al inventario actual", "Reemplazar todo el inventario"])
    
    if archivo is not None:
        try:
            df_subido = pd.read_csv(archivo) if archivo.name.endswith('.csv') else pd.read_excel(archivo)
            st.dataframe(df_subido.head())
            if st.button("✅ Confirmar Carga en Base de Datos"):
                if "Material" in df_subido.columns and "Cantidad" in df_subido.columns:
                    cargar_masivo(df_subido, modo_carga)
                    st.success("¡Inventario cargado exitosamente!")
                    st.rerun()
                else:
                    st.error("El archivo debe contener las columnas 'Material' y 'Cantidad'.")
        except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")

with tabs[4]:
    st.subheader("💬 Asistente Logístico con IA (Gemini)")
    st.markdown("Pregúntale al asistente sobre el stock disponible, qué materiales faltan o ideas logísticas para Weppa.")
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_query = st.chat_input("Ej: ¿Qué material tiene menos stock?")
    if user_query:
        try:
            gemini_key = st.secrets["GEMINI_API_KEY"]
            genai.configure(api_key=gemini_key)
            
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)
            
            df_actual = obtener_inventario()
            datos_contexto = df_actual.to_string(index=False) if not df_actual.empty else "El inventario actual está vacío."
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt_completo = (
                "Eres el asistente logístico experto de Material POP para Weppa. "
                f"Utiliza estrictamente los siguientes datos de inventario:\n{datos_contexto}\n\n"
                f"Pregunta del usuario: {user_query}"
            )
            res = model.generate_content(prompt_completo)
            with st.chat_message("assistant"):
                st.markdown(res.text)
            st.session_state.chat_history.append({"role": "assistant", "content": res.text})
        except Exception as err:
            st.error("⚠️ Error: Configura tu API Key de Gemini en los Secretos de Streamlit Cloud (GEMINI_API_KEY).")
                st.session_state.chat_history.append({"role": "assistant", "content": res.text})
            except Exception as err:
                st.error(f"Error al conectar con Gemini: {err}")
