import streamlit as st
import pandas as pd
import math

# Eigene Module laden
from hydraulik.widerstand import berechne_hydraulischen_widerstand
from system.parallel import simuliere_parallel
from system.parallel_drossel import simuliere_parallel_drossel
from hydraulik.netzwerk import analysiere_gesamte_topologie, berechne_feed_widerstaende

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")

# --- 1. SESSION STATE INITIALISIERUNG ---
if 'p_flow_lh' not in st.session_state: st.session_state.p_flow_lh = 568.0
if 'p_flow_m3' not in st.session_state: st.session_state.p_flow_m3 = 13.63
if 'feed_us' not in st.session_state: st.session_state.feed_us = 160.0
if 'feed_ppm' not in st.session_state: st.session_state.feed_ppm = 96.0

# Synchronisierungs-Logik
def sync_m3(): st.session_state.p_flow_lh = st.session_state.p_flow_m3 * (1000 / 24)
def sync_lh(): st.session_state.p_flow_m3 = st.session_state.p_flow_lh * (24 / 1000)

def sync_ppm_to_us():
    # Faktor 0.6 für reales Wasser
    st.session_state.feed_us = st.session_state.feed_ppm / 0.6
def sync_us_to_ppm():
    st.session_state.feed_ppm = st.session_state.feed_us * 0.6

# --- 2. SIDEBAR EINGABEN ---
with st.sidebar:
    st.title("⚙️ Parameter")
    
    with st.expander("1. Verschaltung & Modus", expanded=True):
        auslegungs_modus = st.radio("Auslegungs-Modus", ["Ziel-Ausbeute vorgeben", "Drossel-Ø vorgeben (Digital Twin)"], key="auslegungs_modus")
        if auslegungs_modus == "Ziel-Ausbeute vorgeben":
            ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 95, 50)
            drossel_vorgabe_mm = 0
        else:
            drossel_vorgabe_mm = st.number_input("Fester Drossel-Ø (mm)", min_value=0.01, value=1.2, step=0.1)
            ausbeute_pct = 0
    
    with st.expander("2. Membrane & System", expanded=True):
        st.markdown("**Datenblatt-Werte (Labor NaCl)**")
        m_flaeche = st.number_input("Filterfläche (m²)", min_value=0.1, value=7.6, step=0.1)
        
        c1, c2 = st.columns(2)
        with c1: st.number_input("Permeat Flow (l/h)", key='p_flow_lh', on_change=sync_lh)
        with c2: st.number_input("Permeat Flow (m³/d)", key='p_flow_m3', on_change=sync_m3)
            
        m_test_flow_effektiv = st.session_state.p_flow_lh * (1.0 + (st.number_input("Alterung (%)", value=-5.0)/100))
        
        cp, cr = st.columns(2)
        with cp: m_test_druck = st.number_input("Test-Druck (bar)", value=9.3)
        with cr: m_rueckhalt = st.number_input("Rejection (%)", value=98) / 100.0
            
        m_test_tds = st.number_input("Test-Lösung (ppm NaCl)", value=500)
        # Wissenschaftlicher Umrechnungsfaktor NaCl ca. 0.5
        st.caption(f"💡 Entspricht Labor-Leitwert: **{m_test_tds / 0.5:.0f} µS/cm**")

        st.divider()
        st.markdown("**Reale Bedingungen (Leitungswasser)**")
        
        u1, u2 = st.columns(2)
        with u1: st.number_input("Feed Leitwert (µS/cm)", key='feed_us', on_change=sync_us_to_ppm)
        with u2: st.number_input("Feed TDS (ppm)", key='feed_ppm', on_change=sync_ppm_to_us)
        
        tds_feed = st.session_state.feed_ppm
        temp = st.slider("Temperatur (°C)", 1, 50, 13)
        trocken_modus = st.checkbox("Trocken-Membran (Dry)", value=False)
        
        if auslegungs_modus == "Ziel-Ausbeute vorgeben":
            p_system = st.number_input("Systemdruck (bar)", value=9.4)
            pump_cfg = {"mode": None, "p_max": 0, "q_max": 0, "p_fix": p_system, "p_z": 0}
        else:
            pump_mode = st.radio("Druck-Ermittlung", ["Manometer", "Kennlinie"])
            p_z = st.number_input("Zulaufdruck (bar)", value=3.0)
            if pump_mode == "Manometer":
                p_fix = st.number_input("Manometerdruck (bar)", value=9.4)
                pump_cfg = {"mode": "Manometer", "p_max": 0, "q_max": 0, "p_fix": p_fix, "p_z": p_z}
            else:
                p_max = st.number_input("Max. Druck (bar)", value=11.5)
                q_max = st.number_input("Max. Flow (l/h)", value=1920.0)
                pump_cfg = {"mode": "Kennlinie", "p_max": p_max, "q_max": q_max, "p_z": p_z}

    # Restliche Sidebar-Strukturen (Rohre) bleiben gleich...
    # (In der Implementierung hier verkürzt)
    saug_cfg = {"d": 13.2, "l": 1000, "b": 0}
    druck_cfg = {"d": 13.2, "l": 400, "b": 0}
    netzwerk_cfg = {"hat_t_stueck": False}
    konz_zweige = [{"d": 10, "l": 100, "b": 0}]
    konz_out = {"d": 10, "l": 300, "b": 2}
    perm_zweige = [{"d": 13.2, "l": 300, "b": 0}]
    perm_out = {"d": 13.2, "l": 1000, "b": 0}
    perm_schlauch = {"d": 13.2, "l": 1, "h": 0}

# --- 3. BERECHNUNG ---
from hydraulik.netzwerk import analysiere_gesamte_topologie
hydraulik = analysiere_gesamte_topologie(saug_cfg, druck_cfg, netzwerk_cfg, konz_zweige, konz_out, perm_zweige, perm_out, perm_schlauch)

if auslegungs_modus == "Ziel-Ausbeute vorgeben":
    # 3x Simulation für Toleranzen
    ergebnisse_ideal = simuliere_parallel(hydraulik, ausbeute_pct, m_flaeche, m_test_flow_effektiv, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, p_system)
    ergebnisse_min = simuliere_parallel(hydraulik, ausbeute_pct, m_flaeche, m_test_flow_effektiv*0.82, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, p_system)
    ergebnisse_max = simuliere_parallel(hydraulik, ausbeute_pct, m_flaeche, m_test_flow_effektiv*1.18, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, p_system)
else:
    ergebnisse_ideal = simuliere_parallel_drossel(hydraulik, drossel_vorgabe_mm, m_flaeche, m_test_flow_effektiv, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, pump_cfg["mode"], pump_cfg["p_max"], pump_cfg["q_max"], pump_cfg["p_z"], pump_cfg.get("p_fix", 0))
    ergebnisse_min = simuliere_parallel_drossel(hydraulik, drossel_vorgabe_mm, m_flaeche, m_test_flow_effektiv*0.82, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, pump_cfg["mode"], pump_cfg["p_max"], pump_cfg["q_max"], pump_cfg["p_z"], pump_cfg.get("p_fix", 0))
    ergebnisse_max = simuliere_parallel_drossel(hydraulik, drossel_vorgabe_mm, m_flaeche, m_test_flow_effektiv*1.18, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, pump_cfg["mode"], pump_cfg["p_max"], pump_cfg["q_max"], pump_cfg["p_z"], pump_cfg.get("p_fix", 0))

# --- 4. ANZEIGE ---
st.title("💧 RO-Anlagen Planer")

if not ergebnisse_ideal.get("error"):
    st.subheader("📊 Performance & Leitwerte (±18%)")
    
    # Helfer für die Zeilen
    def us_ppm(ppm): return f"{ppm/0.6:.1f} µS/cm ({ppm:.1f} ppm)"

    h1, h2, h3, h4 = st.columns([2, 1, 1, 1])
    h2.markdown("**Min (-18%)**")
    h3.markdown("**Idealwert**")
    h4.markdown("**Max (+18%)**")
    st.divider()

    col_l, col1, col2, col3 = st.columns([2, 1, 1, 1])
    col_l.markdown("**Permeatfluss**")
    col1.write(f"{ergebnisse_min['total_permeat']:.1f} l/h")
    col2.write(f"**{ergebnisse_ideal['total_permeat']:.1f} l/h**")
    col3.write(f"{ergebnisse_max['total_permeat']:.1f} l/h")

    col_l, col1, col2, col3 = st.columns([2, 1, 1, 1])
    col_l.markdown("**Konzentratfluss**")
    col1.write(f"{ergebnisse_min['end_konzentrat_flow']:.1f} l/h")
    col2.write(f"**{ergebnisse_ideal['end_konzentrat_flow']:.1f} l/h**")
    col3.write(f"{ergebnisse_max['end_konzentrat_flow']:.1f} l/h")

    col_l, col1, col2, col3 = st.columns([2, 1, 1, 1])
    col_l.markdown("**Permeat Qualität**")
    col1.write(us_ppm(ergebnisse_min['total_permeat_tds']))
    col2.write(f"**{us_ppm(ergebnisse_ideal['total_permeat_tds'])}**")
    col3.write(us_ppm(ergebnisse_max['total_permeat_tds']))

    col_l, col1, col2, col3 = st.columns([2, 1, 1, 1])
    col_l.markdown("**Konzentrat Qualität**")
    col1.write(us_ppm(ergebnisse_min['final_konzentrat_tds']))
    col2.write(f"**{us_ppm(ergebnisse_ideal['final_konzentrat_tds'])}**")
    col3.write(us_ppm(ergebnisse_max['final_konzentrat_tds']))
