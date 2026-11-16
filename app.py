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
            
            st.error("⚠️ Error: Configura tu API Key de Gemini en los Secretos de Streamlit Cloud (GEMINI_API_KEY).")
        except Exception as err:
            st.error("⚠️ Error: Configura tu API Key de Gemini en los Secretos de Streamlit Cloud (GEMINI_API_KEY).")
