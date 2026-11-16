import os
import json
import sqlite3
from datetime import date, datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import streamlit as st
from openai import OpenAI

# ==========================================
# 0. CONFIGURACIÓN DE ACCESO Y ESTILOS
# ==========================================
USUARIOS_AUTORIZADOS = {
    "adm": "weppa2026",
    "angela@weppa.io": "angela2026",
    "omar@weppa.io": "omar2026",
    "maribel@weppa.io": "maribel2026"
}

EMAILS_EQUIPO = ["angela@weppa.io", "omar@weppa.io", "maribel@weppa.io"]

BANNER_PATH = "banner_weppa_custom.png"
BACKGROUND_PATH = "background_weppa_custom.png"
ZOOM_EXCEL_PATH = "agencias_zoom_personalizadas.xlsx"

OPCIONES_CANTIDAD = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    25, 30, 40, 50, 75, 100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500,
    2000, 2500, 3000, 4000, 5000, 7500, 10000
]

ESTADOS_VENEZUELA = [
    "Seleccione un estado...",
    "Amazonas", "Anzoátegui", "Apure", "Aragua", "Barinas", "Bolívar",
    "Carabobo", "Cojedes", "Delta Amacuro", "Dependencias Federales",
    "Distrito Capital", "Falcón", "Guárico", "La Guaira", "Lara",
    "Mérida", "Miranda", "Monagas", "Nueva Esparta", "Portuguesa",
    "Sucre", "Táchira", "Trujillo", "Yaracuy", "Zulia"
]

PREFIJOS_TELEFONO = ["0412", "0414", "0424", "0416", "0426", "0212", "Otro"]

CATALOGO_MATERIALES_BASE = [
    {"Material_ID": "POP-001", "Material": "Stand", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-002", "Material": "Pendón grande", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-003", "Material": "Lanyards", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-004", "Material": "Vasos térmicos", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-005", "Material": "Dummies", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-006", "Material": "Portateléfono redondo", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-007", "Material": "Portateléfono cuadrado", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-008", "Material": "Gobos y portaglobos", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-009", "Material": "Kits pequeños", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-010", "Material": "Kits grandes", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-011", "Material": "Visera de gorras", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-012", "Material": "Chupis", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-013", "Material": "Habladores", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""},
    {"Material_ID": "POP-014", "Material": "Bolsas de tela", "Cantidad": 0, "Medidas_especificaciones": "", "Observaciones": ""}
]

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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS solicitudes_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_solicitud TEXT NOT NULL,
                fecha_solicitud TEXT NOT NULL,
                solicitado_por TEXT NOT NULL,
                cargo_departamento TEXT,
                canal_area TEXT,
                tipo_solicitud TEXT,
                prioridad TEXT,
                fecha_entrega TEXT,
                contacto_solicitante TEXT,
                nombre_tienda TEXT,
                tienda_nueva TEXT,
                descripcion_evento TEXT,
                fechas_evento TEXT,
                aliado_comercial TEXT,
                nombre_promotor TEXT,
                zona_cobertura TEXT,
                activacion_asignada TEXT,
                objetivo_solicitud TEXT,
                detalle_adicional TEXT,
                estado_destino TEXT,
                ciudad_destino TEXT,
                oficina_zoom TEXT,
                direccion_localidad TEXT,
                municipio TEXT,
                parroquia TEXT,
                nombre_retiro TEXT,
                cedula_retiro TEXT,
                telefono_retiro TEXT,
                correo_retiro TEXT,
                referencia_ubicacion TEXT,
                horario_retiro TEXT,
                observaciones_entrega TEXT,
                cantidad_total INTEGER,
                materiales_json TEXT,
                estatus TEXT NOT NULL
            )
        """)

init_db()

# ==========================================
# FUNCIÓN DE NOTIFICACIÓN POR CORREO
# ==========================================
def enviar_correo_notificacion(asunto, cuerpo):
    if "SMTP_USER" in st.secrets and "SMTP_PASSWORD" in st.secrets:
        try:
            remitente = st.secrets["SMTP_USER"]
            password = st.secrets["SMTP_PASSWORD"]
            servidor_smtp = st.secrets.get("SMTP_SERVER", "smtp.gmail.com")
            puerto_smtp = int(st.secrets.get("SMTP_PORT", 587))

            msg = MIMEMultipart()
            msg['From'] = remitente
            msg['Subject'] = asunto
            msg['To'] = ", ".join(EMAILS_EQUIPO)
            
            msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))

            with smtplib.SMTP(servidor_smtp, puerto_smtp) as server:
                server.starttls()
                server.login(remitente, password)
                server.sendmail(remitente, EMAILS_EQUIPO, msg.as_string())
        except Exception as e:
            print(f"Error enviando correo: {e}")

# ==========================================
# ESTILOS CSS AVANZADOS
# ==========================================
bg_css = ""
if os.path.exists(BACKGROUND_PATH):
    import base64
    with open(BACKGROUND_PATH, "rb") as f:
        data_bg = base64.b64encode(f.read()).decode("utf-8")
    bg_css = f"""
    .stApp {{
        background-image: linear-gradient(rgba(10, 10, 10, 0.82), rgba(10, 10, 10, 0.88)), url("data:image/png;base64,{data_bg}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    """
else:
    bg_css = """
    .stApp {
        background-color: #121212;
    }
    """

st.markdown(f"""
    <style>
        {bg_css}
        .stExpander, div[data-testid="stVerticalBlock"] > div > div.stTextInput, div[data-testid="stSelectbox"] {{
            background-color: rgba(25, 25, 25, 0.85);
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.15);
        }}
        h1, h2, h3, h4, h5, h6, p, span, label, div {{
            color: #f1f1f1 !important;
        }}
        .stButton>button {{
            border-radius: 8px;
            font-weight: 600;
            background-color: #ff4b4b;
            color: white !important;
            border: none;
        }}
        .stButton>button:hover {{
            background-color: #ff2b2b;
        }}
    </style>
""", unsafe_allow_html=True)

if os.path.exists(BANNER_PATH):
    st.image(BANNER_PATH, use_container_width=True)

# ==========================================
# 2. NAVEGACIÓN
# ==========================================
modo_vista = st.sidebar.radio(
    "Navegación",
    ["📋 Solicitar Material POP (Externo)", "🔐 Iniciar Sesión (Equipo)"]
)

if modo_vista == "📋 Solicitar Material POP (Externo)":
    st.title("📋 Solicitud de Material POP — Weppa")
    st.markdown("Complete la información. Al seleccionar el **Estado** y la **Agencia**, los campos de dirección, municipio, parroquia y código se rellenarán automáticamente.")

    if "solicitud_enviada_ok" not in st.session_state:
        st.session_state.solicitud_enviada_ok = None

    if st.session_state.solicitud_enviada_ok:
        st.success(f"✅ **¡Solicitud enviada con éxito!**\n\n**Código de solicitud:** `{st.session_state.solicitud_enviada_ok}`\n\n**Estatus actual:** Recepción de Documento.")
        if st.button("Hacer otra solicitud"):
            st.session_state.solicitud_enviada_ok = None
            st.rerun()
        st.stop()

    def actualizar_datos_agencia():
        agencia_elegida = st.session_state.get("sel_agencia_zoom", "")
        estado_actual = st.session_state.get("sel_estado_destino", "Seleccione un estado...")
        
        if os.path.exists(ZOOM_EXCEL_PATH) and agencia_elegida and agencia_elegida != "Seleccione agencia Zoom...":
            try:
                df_z = pd.read_excel(ZOOM_EXCEL_PATH)
                df_z.columns = [str(c).strip() for c in df_z.columns]
                
                df_filtro = df_z[(df_z['Estado'].astype(str).str.strip().str.lower() == estado_actual.lower()) & 
                                 (df_z['Agencia'].astype(str).str.strip() == agencia_elegida)]
                
                if not df_filtro.empty:
                    row = df_filtro.iloc[0]
                    st.session_state.input_dir = str(row.get('Direccion', '')) if pd.notna(row.get('Direccion')) else ''
                    st.session_state.input_mun = str(row.get('Municipio', '')) if pd.notna(row.get('Municipio')) else ''
                    st.session_state.input_par = str(row.get('Parroquia', '')) if pd.notna(row.get('Parroquia')) else ''
                    codigo_val = str(row.get('Codigo', '')) if pd.notna(row.get('Codigo')) else ''
                    st.session_state.input_oficina_completa = f"{agencia_elegida} (Cod: {codigo_val})" if codigo_val else agencia_elegida
                else:
                    st.session_state.input_oficina_completa = agencia_elegida
            except Exception:
                pass

    st.subheader("1. Información general")
    c1, c2, c3 = st.columns(3)
    with c1:
        fecha_solicitud = st.date_input("Fecha de solicitud", value=date.today())
        solicitado_por = st.text_input("Solicitado por *").strip()
        cargo_departamento = st.text_input("Cargo o departamento").strip()
    with c2:
        canal_area = st.text_input("Canal o área").strip()
        tipo_solicitud = st.selectbox("Tipo de solicitud", ["Tienda", "Evento", "Promotor(a)"])
        prioridad = st.selectbox("Prioridad", ["Alta", "Media", "Baja"], index=1)
    with c3:
        fecha_entrega = st.date_input("Fecha requerida de entrega", value=date.today())
        tel_c1, tel_c2 = st.columns([1, 2])
        with tel_c1:
            prefijo_sol = st.selectbox("Prefijo *", PREFIJOS_TELEFONO, key="pref_sol")
        with tel_c2:
            num_sol = st.text_input("Número de contacto *", placeholder="1234567").strip()
        contacto_solicitante = f"{prefijo_sol}-{num_sol}" if num_sol else ""

    st.divider()
    st.subheader("2. Tienda o actividad")
    t1, t2 = st.columns(2)
    with t1:
        nombre_tienda = st.text_input("Nombre de la tienda").strip()
        tienda_nueva = st.selectbox("¿Es tienda nueva?", ["No", "Sí"])
        descripcion_evento = st.text_input("Si es para un evento indique de qué se trata").strip()
        fechas_evento = st.text_input("Fecha o fechas del evento").strip()
        aliado_comercial = st.text_input("Aliado comercial involucrado").strip()
    with t2:
        nombre_promotor = st.text_input("Si es para un promotor indique su nombre").strip()
        zona_cobertura = st.text_input("Zona que cubre").strip()
        activacion_asignada = st.text_input("Evento o activación asignada").strip()
        objetivo_solicitud = st.text_input("Objetivo de la solicitud").strip()
        detalle_adicional = st.text_area("Detalle adicional relevante", height=68).strip()

    st.divider()
    st.subheader("3. Envío por Zoom (Autocompletado Automático)")
    
    df_zoom_excel = pd.DataFrame()
    if os.path.exists(ZOOM_EXCEL_PATH):
        try:
            df_zoom_excel = pd.read_excel(ZOOM_EXCEL_PATH)
            df_zoom_excel.columns = [str(c).strip() for c in df_zoom_excel.columns]
        except Exception:
            pass

    z1, z2, z3 = st.columns(3)
    with z1:
        estado_destino = st.selectbox("Estado de destino *", ESTADOS_VENEZUELA, key="sel_estado_destino")
        ciudad_destino = st.text_input("Ciudad de destino").strip()

        lista_agencias = []
        if not df_zoom_excel.empty and estado_destino != "Seleccione un estado...":
            if 'Estado' in df_zoom_excel.columns and 'Agencia' in df_zoom_excel.columns:
                df_fil = df_zoom_excel[df_zoom_excel['Estado'].astype(str).str.strip().str.lower() == estado_destino.lower()]
                lista_agencias = df_fil['Agencia'].dropna().astype(str).tolist()

        if lista_agencias:
            agencia_sel = st.selectbox("Agencia / Oficina Zoom *", ["Seleccione agencia Zoom..."] + lista_agencias, key="sel_agencia_zoom", on_change=actualizar_datos_agencia)
        else:
            agencia_sel = st.text_input("Agencia Zoom de destino *").strip()

        oficina_zoom = st.session_state.get("input_oficina_completa", agencia_sel if isinstance(agencia_sel, str) else "")

    with z2:
        direccion_localidad = st.text_input("Dirección o localidad", value=st.session_state.get("input_dir", "")).strip()
        municipio = st.text_input("Municipio", value=st.session_state.get("input_mun", "")).strip()
        parroquia = st.text_input("Parroquia", value=st.session_state.get("input_par", "")).strip()
        nombre_retiro = st.text_input("Nombre de quien retirará").strip()

    with z3:
        ci_c1, ci_c2 = st.columns([1, 2])
        with ci_c1:
            tipo_ci = st.selectbox("Tipo CI", ["V-", "E-", "J-"], key="tipo_ci")
        with ci_c2:
            num_ci = st.text_input("Cédula de retiro", placeholder="12345678").strip()
        cedula_retiro = f"{tipo_ci}{num_ci}" if num_ci else ""

        tret_c1, tret_c2 = st.columns([1, 2])
        with tret_c1:
            prefijo_ret = st.selectbox("Prefijo", PREFIJOS_TELEFONO, key="pref_ret")
        with tret_c2:
            num_ret = st.text_input("Teléfono retiro", placeholder="1234567").strip()
        telefono_retiro = f"{prefijo_ret}-{num_ret}" if num_ret else ""
        correo_retiro = st.text_input("Correo electrónico (retiro)").strip()
        referencia_ubicacion = st.text_input("Referencia de ubicación").strip()
        horario_retiro = st.text_input("Horario estimado de retiro").strip()

    observaciones_entrega = st.text_area("Observaciones de entrega", height=68).strip()

    st.divider()
    st.subheader("4. Materiales solicitados")
    st.caption("Haga clic en la celda de 'Cantidad' de cada material para desplegar las opciones numéricas.")
    df_mat_template = pd.DataFrame(CATALOGO_MATERIALES_BASE)
    df_mat_editado = st.data_editor(
        df_mat_template,
        use_container_width=True,
        hide_index=True,
        disabled=["Material_ID", "Material"],
        column_config={
            "Material_ID": st.column_config.TextColumn("ID"),
            "Material": st.column_config.TextColumn("Material"),
            "Cantidad": st.column_config.SelectboxColumn(
                "Cantidad",
                options=OPCIONES_CANTIDAD,
                default=0,
                required=True
            ),
            "Medidas_especificaciones": st.column_config.TextColumn("Medidas / Especificaciones"),
            "Observaciones": st.column_config.TextColumn("Observaciones")
        }
    )

    if st.button("📤 Enviar Solicitud POP"):
        materiales_filtrados = df_mat_editado[df_mat_editado["Cantidad"] > 0]
        cantidad_total = int(materiales_filtrados["Cantidad"].sum())
        estado_final = "" if estado_destino == "Seleccione un estado..." else estado_destino

        if not solicitado_por or not num_sol:
            st.error("⚠️ Complete 'Solicitado por' y 'Número de contacto'.")
        elif estado_destino == "Seleccione un estado...":
            st.error("⚠️ Seleccione un estado de destino.")
        elif cantidad_total <= 0:
            st.error("⚠️ Debe seleccionar al menos 1 material.")
        else:
            codigo_sol = f"POP-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            materiales_json = materiales_filtrados.to_json(orient="records", force_ascii=False)

            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    INSERT INTO solicitudes_v2 (
                        codigo_solicitud, fecha_solicitud, solicitado_por, cargo_departamento,
                        canal_area, tipo_solicitud, prioridad, fecha_entrega, contacto_solicitante,
                        nombre_tienda, tienda_nueva, descripcion_evento, fechas_evento,
                        aliado_comercial, nombre_promotor, zona_cobertura, activacion_asignada,
                        objetivo_solicitud, detalle_adicional, estado_destino, ciudad_destino,
                        oficina_zoom, direccion_localidad, municipio, parroquia, nombre_retiro,
                        cedula_retiro, telefono_retiro, correo_retiro, referencia_ubicacion,
                        horario_retiro, observaciones_entrega, cantidad_total, materiales_json, estatus
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    codigo_sol, str(fecha_solicitud), solicitado_por, cargo_departamento,
                    canal_area, tipo_solicitud, prioridad, str(fecha_entrega), contacto_solicitante,
                    nombre_tienda, tienda_nueva, descripcion_evento, fechas_evento,
                    aliado_comercial, nombre_promotor, zona_cobertura, activacion_asignada,
                    objetivo_solicitud, detalle_adicional, estado_final, ciudad_destino,
                    oficina_zoom, direccion_localidad, municipio, parroquia, nombre_retiro,
                    cedula_retiro, telefono_retiro, correo_retiro, referencia_ubicacion,
                    horario_retiro, observaciones_entrega, cantidad_total, materiales_json, "Recepción de Documento"
                ))
                conn.commit()

            asunto_mail = f"📥 Nueva Solicitud POP Recibida: {codigo_sol} ({solicitado_por})"
            cuerpo_mail = f"Se ha registrado una nueva solicitud de material POP en el sistema.\n\nCódigo: {codigo_sol}\nSolicitante: {solicitado_por}\nDestino: {estado_destino}, {ciudad_destino} ({oficina_zoom})\nTotal piezas: {cantidad_total}\nEstatus inicial: Recepción de Documento"
            enviar_correo_notificacion(asunto_mail, cuerpo_mail)

            st.session_state.solicitud_enviada_ok = codigo_sol
            st.rerun()
    st.stop()

# ==========================================
# 3. LOGIN Y EQUIPO INTERNO
# ==========================================
if not st.session_state.autenticado:
    st.title("🔒 Acceso Corporativo — Control POP Weppa")
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
                st.error("❌ Credenciales incorrectas.")
    st.stop()

def obtener_inventario():
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT id, producto AS 'Material', categoria AS 'Categoría', cantidad AS 'Cantidad', ubicacion AS 'Ubicación' FROM inventario", conn)
    return df

def obtener_solicitudes():
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM solicitudes_v2 ORDER BY id DESC", conn)
    return df

def actualizar_estatus_solicitud(sol_id, nuevo_estatus):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT codigo_solicitud, solicitado_por, estatus, materiales_json FROM solicitudes_v2 WHERE id = ?", (sol_id,))
        row = cursor.fetchone()
        if not row:
            return
        codigo_sol, solicitado_por, estatus_anterior, materiales_json = row[0], row[1], row[2], row[3]
        
        if nuevo_estatus == "Enviado" and estatus_anterior != "Enviado":
            try:
                mats_list = json.loads(materiales_json)
                for item in mats_list:
                    prod_nombre = item["Material"]
                    cant_solicitada = int(item["Cantidad"])
                    cursor.execute("SELECT cantidad FROM inventario WHERE producto = ?", (prod_nombre,))
                    inv_row = cursor.fetchone()
                    if inv_row:
                        stock_actual = inv_row[0]
                        nuevo_stock = max(0, stock_actual - cant_solicitada)
                        cursor.execute("UPDATE inventario SET cantidad = ? WHERE producto = ?", (nuevo_stock, prod_nombre))
                    cursor.execute("INSERT INTO historial (producto, tipo_movimiento, cantidad, usuario) VALUES (?, ?, ?, ?)",
                                   (prod_nombre, "Salida Automática (Solicitud Enviada)", cant_solicitada, st.session_state.usuario_actual))
            except Exception as e:
                st.error(f"Error descontando inventario: {e}")
                
        cursor.execute("UPDATE solicitudes_v2 SET estatus = ? WHERE id = ?", (nuevo_estatus, sol_id))
        conn.commit()

    asunto_mail = f"🔄 Actualización de Estatus POP: {codigo_sol} ➔ {nuevo_estatus}"
    cuerpo_mail = f"La solicitud {codigo_sol} de {solicitado_por} ha cambiado de estatus.\n\nNuevo Estatus: {nuevo_estatus}\nModificado por: {st.session_state.usuario_actual}"
    enviar_correo_notificacion(asunto_mail, cuerpo_mail)

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
    return True, f"¡{tipo} registrada con éxito!"

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

with st.sidebar:
    st.write(f"👤 Conectado como:\n**{st.session_state.usuario_actual}**")
    if st.session_state.usuario_actual == "adm":
        st.divider()
        st.markdown("### 🎨 Personalización Visual")
        banner_subido = st.file_uploader("Subir Banner Superior", type=["png", "jpg", "jpeg"])
        if banner_subido is not None:
            with open(BANNER_PATH, "wb") as f:
                f.write(banner_subido.getbuffer())
            st.success("¡Banner actualizado!")
            st.rerun()

        if os.path.exists(BANNER_PATH):
            if st.button("🗑️ Eliminar Banner"):
                os.remove(BANNER_PATH)
                st.rerun()

        st.markdown("---")
        bg_subido = st.file_uploader("Subir Imagen de Fondo", type=["png", "jpg", "jpeg"])
        if bg_subido is not None:
            with open(BACKGROUND_PATH, "wb") as f:
                f.write(bg_subido.getbuffer())
            st.success("¡Fondo actualizado!")
            st.rerun()

        if os.path.exists(BACKGROUND_PATH):
            if st.button("🗑️ Eliminar Fondo"):
                os.remove(BACKGROUND_PATH)
                st.rerun()

        st.divider()
        st.markdown("### 📦 Agencias Zoom (Excel)")
        zoom_subido = st.file_uploader("Actualizar Excel Zoom", type=["xlsx", "csv"])
        if zoom_subido is not None:
            try:
                df_z = pd.read_csv(zoom_subido) if zoom_subido.name.endswith('.csv') else pd.read_excel(zoom_subido)
                df_z.to_excel(ZOOM_EXCEL_PATH, index=False)
                st.success("¡Excel de agencias Zoom cargado con éxito!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

        if os.path.exists(ZOOM_EXCEL_PATH):
            if st.button("🗑️ Eliminar Excel Zoom"):
                os.remove(ZOOM_EXCEL_PATH)
                st.rerun()

    st.divider()
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

st.title("📦 Control de Material POP — Weppa (Panel Interno)")

tabs = st.tabs([
    "📥 Solicitudes Externas",
    "📊 Panel de Estatus (Recepción/Proceso/Envío)",
    "📊 Inventario Actual",
    "➕ Registro Individual",
    "📂 Cargar / Descargar Excel",
    "🤖 Asistente IA ChatGPT"
])

with tabs[0]:
    st.subheader("📥 Gestión y Ciclo de Solicitudes POP")
    df_sol = obtener_solicitudes()
    if not df_sol.empty:
        st.download_button("⬇️ Descargar Reporte (CSV)", data=df_sol.drop(columns=["materiales_json"]).to_csv(index=False).encode("utf-8"), file_name="solicitudes.csv", mime="text/csv")
        st.divider()
        for _, row in df_sol.iterrows():
            estatus_actual = row['estatus']
            with st.expander(f"[{estatus_actual}] {row['codigo_solicitud']} — Solicitante: {row['solicitado_por']} | ({row['cantidad_total']} piezas)"):
                st.write(f"**Destino:** {row['estado_destino']}, {row['ciudad_destino']} — **Oficina:** {row['oficina_zoom']}")
                st.write(f"**Dirección:** {row['direccion_localidad']} (Mun: {row['municipio']}, Parr: {row['parroquia']})")
                try:
                    st.dataframe(pd.read_json(row["materiales_json"]), use_container_width=True, hide_index=True)
                except Exception:
                    pass
                
                fases_estatus = ["Recepción de Documento", "Proceso", "Enviado"]
                idx_actual = fases_estatus.index(estatus_actual) if estatus_actual in fases_estatus else 0
                
                if st.session_state.usuario_actual == "adm":
                    nuevo_est = st.selectbox("Actualizar Estatus (Control exclusivo de Admin)", fases_estatus, index=idx_actual, key=f"sel_{row['id']}")
                    if st.button("Guardar Estatus", key=f"btn_{row['id']}"):
                        actualizar_estatus_solicitud(row["id"], nuevo_est)
                        st.success(f"✅ Estatus actualizado a '{nuevo_est}' y notificación enviada.")
                        st.rerun()
                else:
                    st.info(f"Estatus actual: **{estatus_actual}** (Solo el administrador 'adm' puede modificar las fases).")
    else:
        st.info("No hay solicitudes registradas.")

with tabs[1]:
    st.subheader("📊 Tablero de Trazabilidad: Recepción, Proceso y Envío")
    st.markdown("Visualice el estatus en tiempo real de todas las solicitudes distribuidas en sus tres fases operativas.")
    
    df_tablero = obtener_solicitudes()
    if not df_tablero.empty:
        fases = ["Recepción de Documento", "Proceso", "Enviado"]
        colores_fase = {"Recepción de Documento": "📥", "Proceso": "⚙️", "Enviado": "🚚"}
        
        cols_tablero = st.columns(3)
        for i, fase in enumerate(fases):
            with cols_tablero[i]:
                st.markdown(f"### {colores_fase[fase]} {fase}")
                df_fase = df_tablero[df_tablero['estatus'] == fase]
                st.metric(f"Total en {fase}", len(df_fase))
                st.divider()
                
                for _, r in df_fase.iterrows():
                    with st.container():
                        st.markdown(f"**`{r['codigo_solicitud']}`**")
                        st.write(f"👤 **Solicitante:** {r['solicitado_por']}")
                        st.write(f"🏢 **Oficina:** {r['oficina_zoom']}")
                        st.write(f"📦 **Piezas:** {r['cantidad_total']}")
                        
                        if st.session_state.usuario_actual == "adm":
                            nuevo_cambio = st.selectbox("Cambiar fase", fases, index=fases.index(r['estatus']), key=f"board_{r['id']}")
                            if nuevo_cambio != r['estatus']:
                                if st.button("Actualizar fase", key=f"b_upd_{r['id']}"):
                                    actualizar_estatus_solicitud(r['id'], nuevo_cambio)
                                    st.success("¡Estatus actualizado y notificación enviada!")
                                    st.rerun()
                        else:
                            st.caption(f"Fase: {r['estatus']}")
                        st.markdown("---")
    else:
        st.info("No hay solicitudes para mostrar en el tablero.")

with tabs[2]:
    df = obtener_inventario()
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Variedad de Materiales", len(df))
        with col2:
            st.metric("Total Unidades Disponibles", int(df['Cantidad'].sum()))
        st.divider()
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Inventario vacío.")

with tabs[3]:
    st.subheader("➕ Registro Individual")
    with st.form("form_pop"):
        producto = st.text_input("Material").strip()
        categoria = st.selectbox("Categoría", ["Textil", "Papelería", "Accesorios", "Eventos", "Merchandising"])
        cantidad = st.selectbox("Cantidad", OPCIONES_CANTIDAD[1:])
        tipo = st.radio("Operación", ["Entrada", "Salida"])
        ubicacion = st.text_input("Ubicación", value="Almacén Principal")
        if st.form_submit_button("Guardar"):
            ok, msg = registrar_movimiento(producto, categoria, cantidad, tipo, ubicacion)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

with tabs[4]:
    st.subheader("📂 Inventario Masivo")
    archivo = st.file_uploader("Subir inventario", type=["xlsx", "csv"])
    modo_carga = st.radio("Modo", ["Sumar al inventario actual", "Reemplazar todo el inventario"])
    if archivo is not None:
        if st.button("Confirmar Carga"):
            df_subido = pd.read_csv(archivo) if archivo.name.endswith('.csv') else pd.read_excel(archivo)
            cargar_masivo(df_subido, modo_carga)
            st.success("Cargado con éxito.")
            st.rerun()

with tabs[5]:
    st.subheader("💬 Asistente IA")
    user_query = st.chat_input("Pregunta algo sobre el inventario...")
    if user_query:
        if "OPENAI_API_KEY" not in st.secrets:
            st.error("Configure OPENAI_API_KEY en Streamlit Secrets.")
        else:
            client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
            response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": user_query}])
            st.markdown(response.choices[0].message.content)
