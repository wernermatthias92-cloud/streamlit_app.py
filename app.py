import streamlit as st
import pandas as pd
import math

from hydraulik.widerstand import berechne_hydraulischen_widerstand
from system.parallel import simuliere_parallel
from system.parallel_drossel import simuliere_parallel_drossel
from hydraulik.netzwerk import analysiere_gesamte_topologie
from utils.pdf_export import generiere_pdf

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")

# --- UI SYNC LOGIK (l/h <-> m³/d) ---
if 'p_flow_lh' not in st.session_state:
    st.session_state.p_flow_lh = 568.0
if 'p_flow_m3' not in st.session_state:
    st.session_state.p_flow_m3 = 13.63

def sync_m3():
    st.session_state.p_flow_lh = st.session_state.p_flow_m3 * (1000 / 24)
def sync_lh():
    st.session_state.p_flow_m3 = st.session_state.p_flow_lh * (24 / 1000)

with st.sidebar:
    with st.expander("1. Verschaltung & Aufbau", expanded=True):
        st.info("🔧 Modus: Parallele Verschaltung (aktiv)")
        schaltung = "Parallel (Aufteilung)"
        
        auslegungs_modus = st.radio("Auslegungs-Modus", ["Ziel-Ausbeute vorgeben", "Drossel-Ø vorgeben (Digital Twin)"])
        
        if auslegungs_modus == "Ziel-Ausbeute vorgeben":
            ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 90, 50)
            drossel_vorgabe_mm = 0
        else:
            drossel_vorgabe_mm = st.number_input("Fester Drossel-Ø (mm)", min_value=0.1, value=1.2, step=0.1)
            ausbeute_pct = 0
    
    with st.expander("2. Membrane & System", expanded=True):
        st.markdown("**Datenblatt-Parameter (zz.B. XE3-4040)**")
        
        # Filterfläche (aus Datenblättern oft 7.0 - 8.0 m² für 4040er)
        m_flaeche = st.number_input("Aktive Filterfläche (m²)", min_value=0.1, value=7.6, step=0.1)
        
        # Gekoppelte Inputs für l/h und m³/d
        col1, col2 = st.columns(2)
        with col1:
            st.number_input("Permeat Flow (l/h)", key='p_flow_lh', on_change=sync_lh)
        with col2:
            st.number_input("Permeat Flow (m³/d)", key='p_flow_m3', on_change=sync_m3)
            
        m_test_flow_datasheet = st.session_state.p_flow_lh
        
        # Alterungstoleranz
        m_toleranz_pct = st.number_input("Leistungs-Toleranz / Alterung (%)", min_value=-50.0, max_value=20.0, value=-5.0, step=1.0)
        m_test_flow_effektiv = m_test_flow_datasheet * (1.0 + (m_toleranz_pct / 100.0))
        
        # Test-Parameter aus Datenblatt
        c_p, c_r = st.columns(2)
        with c_p:
            m_test_druck = st.number_input("Test-Druck (bar)", value=9.3, format="%.1f", step=0.1)
        with c_r:
            m_rueckhalt_int = st.number_input("Nominal Rejection (%)", min_value=0, max_value=100, value=98, step=1, format="%d")
            m_rueckhalt = m_rueckhalt_int / 100.0
            
        m_test_tds = st.number_input("Test-Lösung (ppm)", value=500, step=50)

        st.divider()
        st.markdown("**Reale Einsatzbedingungen**")
        tds_feed = st.number_input("Feed TDS real (ppm)", value=96)
        temp = st.slider("Wassertemperatur real (°C)", 1, 50, 13)
        
        st.divider()
        if auslegungs_modus == "Ziel-Ausbeute vorgeben":
            p_system = st.number_input("Statischer Systemdruck nach Pumpe (bar)", value=9.4, step=0.1, format="%.1f")
            pumpe_p_max, pumpe_q_max = p_system, 0 
        else:
            pumpe_p_max = st.number_input("Max. Druck bei 0 l/h (bar)", value=11.5, step=0.5, format="%.1f")
            pumpe_q_max = st.number_input("Max. Durchfluss bei 0 bar (l/h)", value=2500.0, step=100.0)
            p_system = pumpe_p_max 
            
# --- HIER GEHT DIE APP.PY MIT EXPANDER 3 WEITER WIE GEHABT ---
