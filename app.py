import os
import json
import sqlite3
from datetime import date, datetime
import pandas as pd
import streamlit as st
import google.generativeai as genai

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
        st.success(f"✅ **¡Solicitud enviada con éxito!**\n\n**Código de solicitud:** `{st.session_state.solicitud_enviada_ok}`\n\n**Estatus:** Enviado (Recibido por el equipo de Weppa).")
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

        st.
            st.error("⚠️ Error: Configura tu API Key de Gemini en los Secretos de Streamlit Cloud (GEMINI_API_KEY).")
        except Exception as err:
            st.error("⚠️ Error: Configura tu API Key de Gemini en los Secretos de Streamlit Cloud (GEMINI_API_KEY).")
