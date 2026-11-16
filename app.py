import os
import json
import sqlite3
from datetime import date, datetime
import pandas as pd
import streamlit as st
from openai import OpenAI

# ==========================================
# 0. CONFIGURACIÓN DE ACCESO, LISTAS Y CATÁLOGO
# ==========================================
USUARIOS_AUTORIZADOS = {
    "adm": "weppa2026",
    "angela@weppa.io": "angela2026",
    "omar@weppa.io": "omar2026",
    "maribel@weppa.io": "maribel2026"
}

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
# 2. NAVEGACIÓN: FORMULARIO PÚBLICO VS EQUIPO
# ==========================================
modo_vista = st.sidebar.radio(
    "Navegación",
    ["📋 Solicitar Material POP (Externo)", "🔐 Iniciar Sesión (Equipo)"]
)

if modo_vista == "📋 Solicitar Material POP (Externo)":
    st.title("📋 Solicitud de Material POP — Weppa")
    st.markdown("Completa las secciones del formulario y selecciona las cantidades en el desplegable de cada material.")

    if "solicitud_enviada_ok" not in st.session_state:
        st.session_state.solicitud_enviada_ok = None

    if st.session_state.solicitud_enviada_ok:
        st.success(f"✅ **¡Solicitud enviada con éxito!**\n\n**Código de solicitud:** `{st.session_state.solicitud_enviada_ok}`\n\n**Estatus inicial:** Recibido (En revisión por el equipo de Weppa).")
        if st.button("Hacer otra solicitud"):
            st.session_state.solicitud_enviada_ok = None
            st.rerun()
        st.stop()

    with st.form("form_solicitud_pop_weppa"):
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
        st.subheader("3. Envío por Zoom")
        z1, z2, z3 = st.columns(3)
        with z1:
            estado_destino = st.selectbox("Estado de destino", ESTADOS_VENEZUELA)
            ciudad_destino = st.text_input("Ciudad de destino").strip()
            oficina_zoom = st.text_input("Oficina Zoom de destino").strip()
            direccion_localidad = st.text_input("Dirección o localidad").strip()
        with z2:
            municipio = st.text_input("Municipio").strip()
            parroquia = st.text_input("Parroquia").strip()
            nombre_retiro = st.text_input("Nombre de quien retirará").strip()
            ci_c1, ci_c2 = st.columns([1, 2])
            with ci_c1:
                tipo_ci = st.selectbox("Tipo", ["V-", "E-", "J-"], key="tipo_ci")
            with ci_c2:
                num_ci = st.text_input("Cédula", placeholder="12345678").strip()
            cedula_retiro = f"{tipo_ci}{num_ci}" if num_ci else ""
        with z3:
            tret_c1, tret_c2 = st.columns([1, 2])
            with tret_c1:
                prefijo_ret = st.selectbox("Prefijo", PREFIJOS_TELEFONO, key="pref_ret")
            with tret_c2:
                num_ret = st.text_input("Teléfono (retiro)", placeholder="1234567").strip()
            telefono_retiro = f"{prefijo_ret}-{num_ret}" if num_ret else ""
            correo_retiro = st.text_input("Correo electrónico (retiro)").strip()
            referencia_ubicacion = st.text_input("Referencia de ubicación").strip()
            horario_retiro = st.text_input("Horario estimado de retiro").strip()
        observaciones_entrega = st.text_area("Observaciones de entrega", height=68).strip()

        st.divider()
        st.subheader("4. Materiales solicitados")
        st.caption("Haz clic en la celda de 'Cantidad' de cada material para desplegar las opciones numéricas.")
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
                    help="Despliega y selecciona la cantidad de piezas",
                    options=OPCIONES_CANTIDAD,
                    default=0,
                    required=True
                ),
                "Medidas_especificaciones": st.column_config.TextColumn("Medidas / Especificaciones"),
                "Observaciones": st.column_config.TextColumn("Observaciones")
            }
        )

        enviar_form = st.form_submit_button("📤 Enviar Solicitud POP")

        if enviar_form:
            materiales_filtrados = df_mat_editado[df_mat_editado["Cantidad"] > 0]
            cantidad_total = int(materiales_filtrados["Cantidad"].sum())
            estado_final = "" if estado_destino == "Seleccione un estado..." else estado_destino

            if not solicitado_por or not num_sol:
                st.error("⚠️ Por favor completa los campos obligatorios: 'Solicitado por' y 'Número de contacto'.")
            elif cantidad_total <= 0:
                st.error("⚠️ Debes seleccionar al menos 1 material con cantidad mayor a 0.")
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
                        horario_retiro, observaciones_entrega, cantidad_total, materiales_json, "Recibido"
                    ))
                    conn.commit()

                st.session_state.solicitud_enviada_ok = codigo_sol
                st.rerun()
    st.stop()

# ==========================================
# 3. LOGIN PARA EL EQUIPO INTERNO
# ==========================================
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
# 4. FUNCIONES DE GESTIÓN INTERNA
# ==========================================
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
        
        # Consultar estatus previo y los materiales de esta solicitud
        cursor.execute("SELECT estatus, materiales_json FROM solicitudes_v2 WHERE id = ?", (sol_id,))
        row = cursor.fetchone()
        if not row:
            return
        estatus_anterior, materiales_json = row[0], row[1]

        # Si el nuevo estatus es "Enviado" y ANTES no estaba en "Enviado", restamos el inventario automáticamente
        if nuevo_estatus == "Enviado" and estatus_anterior != "Enviado":
            try:
                mats_list = json.loads(materiales_json)
                for item in mats_list:
                    prod_nombre = item["Material"]
                    cant_solicitada = int(item["Cantidad"])

                    # Descontar del stock actual
                    cursor.execute("SELECT cantidad FROM inventario WHERE producto = ?", (prod_nombre,))
                    inv_row = cursor.fetchone()
                    if inv_row:
                        stock_actual = inv_row[0]
                        nuevo_stock = max(0, stock_actual - cant_solicitada)
                        cursor.execute("UPDATE inventario SET cantidad = ? WHERE producto = ?", (nuevo_stock, prod_nombre))
                    
                    # Registrar salida en el historial
                    cursor.execute("INSERT INTO historial (producto, tipo_movimiento, cantidad, usuario) VALUES (?, ?, ?, ?)",
                                   (prod_nombre, "Salida Automática (Solicitud)", cant_solicitada, st.session_state.usuario_actual))
            except Exception as e:
                st.error(f"Error descontando inventario: {e}")

        # Actualizar el estatus en la base de datos
        cursor.execute("UPDATE solicitudes_v2 SET estatus = ? WHERE id = ?", (nuevo_estatus, sol_id))
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
# 5. PANEL INTERNO DE ADMINISTRACIÓN
# ==========================================
with st.sidebar:
    st.write(f"👤 Conectado como:\n**{st.session_state.usuario_actual}**")
    if st.button("Cerrar Sesión"):
        st.session_state.autenticado = False
        st.rerun()

st.title("📦 Control de Material POP — Weppa (Panel Interno)")

tabs = st.tabs([
    "📥 Solicitudes Externas",
    "📊 Inventario Actual",
    "➕ Registro Individual",
    "📂 Cargar / Descargar Excel",
    "🤖 Asistente IA ChatGPT"
])

with tabs[0]:
    st.subheader("📥 Solicitudes de Material POP Recibidas")
    df_sol = obtener_solicitudes()

    if not df_sol.empty:
        st.download_button(
            label="⬇️ Descargar Reporte de Solicitudes (CSV)",
            data=df_sol.drop(columns=["materiales_json"]).to_csv(index=False).encode("utf-8"),
            file_name="solicitudes_pop_weppa.csv",
            mime="text/csv"
        )
        st.divider()

        for _, row in df_sol.iterrows():
            titulo_exp = f"[{row['estatus'].upper()}] {row['codigo_solicitud']} — {row['solicitado_por']} | {row['tipo_solicitud']} ({row['cantidad_total']} piezas)"
            with st.expander(titulo_exp):
                col_i1, col_i2, col_i3 = st.columns(3)
                with col_i1:
                    st.markdown("**Información General**")
                    st.write(f"📅 **Fecha solicitud:** {row['fecha_solicitud']}")
                    st.write(f"📆 **Entrega requerida:** {row['fecha_entrega']}")
                    st.write(f"👤 **Solicitante:** {row['solicitado_por']} ({row['cargo_departamento']})")
                    st.write(f"📞 **Contacto:** {row['contacto_solicitante']}")
                    st.write(f"🏢 **Canal/Área:** {row['canal_area']} | **Prioridad:** {row['prioridad']}")
                with col_i2:
                    st.markdown("**Tienda o Actividad**")
                    st.write(f"🏪 **Tienda:** {row['nombre_tienda']} (Nueva: {row['tienda_nueva']})")
                    st.write(f"🎪 **Evento:** {row['descripcion_evento']} ({row['fechas_evento']})")
                    st.write(f"🤝 **Aliado:** {row['aliado_comercial']} | **Promotor:** {row['nombre_promotor']}")
                    st.write(f"📍 **Zona:** {row['zona_cobertura']} | **Activación:** {row['activacion_asignada']}")
                    st.write(f"🎯 **Objetivo:** {row['objetivo_solicitud']}")
                    if row['detalle_adicional']:
                        st.write(f"📝 **Detalle:** {row['detalle_adicional']}")
                with col_i3:
                    st.markdown("**Envío por Zoom**")
                    st.write(f"🗺️ **Destino:** {row['estado_destino']}, {row['ciudad_destino']}")
                    st.write(f"📦 **Oficina Zoom:** {row['oficina_zoom']}")
                    st.write(f"🏠 **Dirección:** {row['direccion_localidad']} ({row['municipio']}, {row['parroquia']})")
                    st.write(f"🪪 **Retira:** {row['nombre_retiro']} (CI: {row['cedula_retiro']})")
                    st.write(f"📱 **Tel/Correo:** {row['telefono_retiro']} | {row['correo_retiro']}")
                    st.write(f"🕒 **Horario/Ref:** {row['horario_retiro']} — {row['referencia_ubicacion']}")
                    if row['observaciones_entrega']:
                        st.write(f"🚚 **Obs. entrega:** {row['observaciones_entrega']}")

                st.markdown("**Detalle de Materiales Solicitados**")
                try:
                    df_mats = pd.read_json(row["materiales_json"])
                    st.dataframe(df_mats, use_container_width=True, hide_index=True)
                except Exception:
                    st.write("Sin detalle de materiales.")

                st.divider()
                col_est1, col_est2 = st.columns([2, 1])
                with col_est1:
                    # Estatus actualizados y ordenados lógicamente
                    opciones_est = ["Recibido", "Aprobado", "Enviado"]
                    idx_actual = opciones_est.index(row["estatus"]) if row["estatus"] in opciones_est else 0
                    nuevo_est = st.selectbox("Actualizar estatus de la solicitud", opciones_est, index=idx_actual, key=f"sel_{row['id']}")
                with col_est2:
                    st.write("")
                    st.write("")
                    if st.button("Guardar Estatus", key=f"btn_{row['id']}"):
                        actualizar_estatus_solicitud(row["id"], nuevo_est)
                        if nuevo_est == "Enviado":
                            st.success(f"Estatus 'Enviado': ¡Inventario descontado automáticamente!")
                        else:
                            st.success(f"Estatus cambiado a '{nuevo_est}'")
                        st.rerun()
    else:
        st.info("No hay solicitudes registradas todavía.")

with tabs[1]:
    df = obtener_inventario()
    if not df.empty:
        col1, col2 = st.columns(2)
        col1.metric("Variedad de Materiales", len(df))
        col2.metric("Total Unidades Disponibles", int(df['Cantidad'].sum()))
        st.dataframe(df, use_container_width=True)
    else:
        st.info("El inventario está vacío. Sube un archivo Excel/CSV o registra materiales.")

with tabs[2]:
    st.subheader("Registrar Entrada o Salida")
    with st.form("form_pop"):
        col_a, col_b = st.columns(2)
        with col_a:
            producto = st.text_input("Nombre del Material", placeholder="Ej: Stand, Lanyards, Vasos térmicos").strip()
            categoria = st.selectbox("Categoría", ["Textil", "Papelería", "Accesorios", "Eventos", "Merchandising"])
            cantidad = st.selectbox("Cantidad", OPCIONES_CANTIDAD[1:])
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
            "Material": ["Stand", "Lanyards"],
            "Categoría": ["Eventos", "Accesorios"],
            "Cantidad": [10, 200],
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
    st.subheader("💬 Asistente Logístico con ChatGPT (OpenAI)")
    st.markdown("Pregúntale al asistente sobre el stock disponible o las solicitudes recibidas utilizando GPT.")

    if "chat_history_openai" not in st.session_state:
        st.session_state.chat_history_openai = []

    for msg in st.session_state.chat_history_openai:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_query = st.chat_input("Ej: ¿Qué material tiene más stock o qué solicitudes hay?")
    if user_query:
        if "OPENAI_API_KEY" not in st.secrets:
            st.error("⚠️ Configura tu 'OPENAI_API_KEY' en los Secretos de Streamlit Cloud.")
        else:
            try:
                client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

                st.session_state.chat_history_openai.append({"role": "user", "content": user_query})
                with st.chat_message("user"):
                    st.markdown(user_query)

                df_actual = obtener_inventario()
                datos_inv = df_actual.to_string(index=False) if not df_actual.empty else "Inventario vacío."

                df_sol_ia = obtener_solicitudes()
                datos_sol = df_sol_ia[["codigo_solicitud", "solicitado_por", "tipo_solicitud", "cantidad_total", "estatus"]].to_string(index=False) if not df_sol_ia.empty else "Sin solicitudes."

                prompt_sistema = (
                    "Eres el asistente logístico experto de Material POP para Weppa. "
                    f"Utiliza estrictamente los siguientes datos:\n\nINVENTARIO:\n{datos_inv}\n\n"
                    f"SOLICITUDES RECIBIDAS:\n{datos_sol}"
                )

                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": prompt_sistema},
                        {"role": "user", "content": user_query}
                    ]
                )

                respuesta_ia = response.choices[0].message.content

                with st.chat_message("assistant"):
                    st.markdown(respuesta_ia)
                st.session_state.chat_history_openai.append({"role": "assistant", "content": respuesta_ia})

            except Exception as err:
                st.error(f"⚠️ Error al conectar con OpenAI: {err}")
