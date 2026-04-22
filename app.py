import streamlit as st
import pandas as pd
import math

from hydraulik.widerstand import berechne_hydraulischen_widerstand
from system.parallel import simuliere_parallel
from system.parallel_drossel import simuliere_parallel_drossel
from hydraulik.netzwerk import berechne_parallel_netzwerk # <-- HIER IST DIE KORREKTUR
from utils.pdf_export import generiere_pdf

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")

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
    
    with st.expander("2. Membrane & System", expanded=False):
        m_flaeche = st.number_input("Filterfläche (m²)", value=7.5)
        m_test_flow_datasheet = st.number_input("Nennleistung laut Datenblatt (l/h)", value=568.0)
        m_toleranz_pct = st.number_input("Leistungs-Toleranz / Alterung (%)", min_value=-50.0, max_value=20.0, value=-5.0, step=1.0)
        m_test_flow_effektiv = m_test_flow_datasheet * (1.0 + (m_toleranz_pct / 100.0))
        
        m_test_druck = st.number_input("Test-Druck (bar)", value=9.3)
        m_rueckhalt = st.slider("Rückhalt (%)", 90.0, 99.9, 98.0) / 100
        tds_feed = st.number_input("Feed TDS (ppm)", value=96)
        temp = st.slider("Temperatur (°C)", 10, 50, 13)
        
        st.divider()
        if auslegungs_modus == "Ziel-Ausbeute vorgeben":
            p_system = st.number_input("Statischer Systemdruck nach Pumpe (bar)", value=9.4)
            pumpe_p_max, pumpe_q_max = p_system, 0 
        else:
            pumpe_p_max = st.number_input("Max. Druck bei 0 Durchfluss (bar)", value=11.5, step=0.5)
            pumpe_q_max = st.number_input("Max. Durchfluss bei 0 bar (l/h)", value=2500.0, step=100.0)
            p_system = pumpe_p_max 

    with st.expander("3. Rohrleitungen Zuleitung", expanded=False):
        p_zulauf = st.number_input("Zulaufdruck (bar)", value=3.0, key="pz")
        d_saug = st.number_input("Ø Innen Saugseite (mm)", value=13.2, key="ds")
        l_saug = st.number_input("Länge (mm)", value=1000.0, key="ls")
        b_saug = st.number_input("Bögen Saugseite", 0, 10, 0)
        r_saug = berechne_hydraulischen_widerstand(d_saug, l_saug, [], b_saug)
        
        st.divider()
        d_druck = st.number_input("Ø Hauptleitung (mm)", value=13.2)
        l_druck = st.number_input("Länge Hauptleitung (mm)", value=400.0)
        b_druck = st.number_input("Bögen Hauptleitung", 0, 10, 0)
        r_druck_haupt = berechne_hydraulischen_widerstand(d_druck, l_druck, [], b_druck)
        
        hat_t_stueck = st.checkbox("Hauptleitung durch T-Stück aufteilen", value=True)
        # Parameter-Sammlung für Netzwerk-Berechnung
        params = {"hat_t_stueck": hat_t_stueck}
        if hat_t_stueck:
            colA, colB = st.columns(2)
            with colA:
                st.markdown("Strang A")
                params.update({"d_a": st.number_input("Ø A", 13.2), "l_a": st.number_input("L A", 150.0), "b_a": st.number_input("B A", 1)})
                sub_a = st.checkbox("A aufteilen")
                params.update({"sub_a": sub_a, "d_a1": 0, "l_a1": 0, "b_a1": 0, "d_a2": 0, "l_a2": 0, "b_a2": 0})
                if sub_a:
                    params.update({"d_a1": st.number_input("Ø A1", 10.0), "l_a1": st.number_input("L A1", 500.0), "b_a1": 0,
                                   "d_a2": st.number_input("Ø A2", 10.0), "l_a2": st.number_input("L A2", 500.0), "b_a2": 0})
            with colB:
                st.markdown("Strang B")
                params.update({"d_b": st.number_input("Ø B", 13.2), "l_b": st.number_input("L B", 150.0), "b_b": st.number_input("B B", 1)})
                sub_b = st.checkbox("B aufteilen", True)
                params.update({"sub_b": sub_b, "d_b1": 0, "l_b1": 0, "b_b1": 0, "d_b2": 0, "l_b2": 0, "b_b2": 0})
                if sub_b:
                    params.update({"d_b1": st.number_input("Ø B1", 13.2), "l_b1": st.number_input("L B1", 200.0), "b_b1": 0,
                                   "d_b2": st.number_input("Ø B2", 13.2), "l_b2": st.number_input("L B2", 200.0), "b_b2": 0})
        else:
            params.update({"d_a": 0, "l_a": 0, "b_a": 0, "sub_a": False, "d_a1": 0, "l_a1": 0, "b_a1": 0, "d_a2": 0, "l_a2": 0, "b_a2": 0,
                           "d_b": 0, "l_b": 0, "b_b": 0, "sub_b": False, "d_b1": 0, "l_b1": 0, "b_b1": 0, "d_b2": 0, "l_b2": 0, "b_b2": 0})

        # Aufruf der ausgelagerten Netzwerk-Logik
        r_netzwerk, flow_fractions, membran_namen = berechne_parallel_netzwerk(**params)
        anzahl_membranen = len(flow_fractions)

    with st.expander("4. Konzentrat- & Permeatleitungen", expanded=False):
        leitungen_konz = []
        for i in range(anzahl_membranen):
            leitungen_konz.append({"d": st.number_input(f"Ø Konz {membran_namen[i]}", 8.4, key=f"ki_{i}"), "l": st.number_input(f"L Konz {i}", 100.0, key=f"kl_{i}"), "b": 0})
        leitung_out = {"d": st.number_input("Ø Konz Sammel", 6.0), "l": st.number_input("L Konz Sammel", 300.0), "b": 2}
        
        p_leitungen_konz = []
        for i in range(anzahl_membranen):
            p_leitungen_konz.append({"d": 13.2, "l": 300.0, "b": 0})
        p_leitung_out = {"d": 13.2, "l": 1000.0, "b": 0}
        p_schlauch_out = {"d": 13.2, "l": 1.0, "h": 0.0}

# --- BERECHNUNG ---
if auslegungs_modus == "Ziel-Ausbeute vorgeben":
    ergebnisse = simuliere_parallel(flow_fractions, membran_namen, ausbeute_pct, m_flaeche, m_test_flow_effektiv, m_test_druck, m_rueckhalt, tds_feed, temp, p_system, r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, leitungen_konz, leitung_out, p_leitungen_konz, p_leitung_out, p_schlauch_out)
else:
    ergebnisse = simuliere_parallel_drossel(flow_fractions, membran_namen, drossel_vorgabe_mm, m_flaeche, m_test_flow_effektiv, m_test_druck, m_rueckhalt, tds_feed, temp, pumpe_p_max, pumpe_q_max, p_zulauf, r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, leitungen_konz, leitung_out, p_leitungen_konz, p_leitung_out, p_schlauch_out)

# UI Ausgabe
st.title("💧 RO-Anlagen Planer")
if ergebnisse.get("error"):
    st.error(ergebnisse["error"])
else:
    c1, c2, c3 = st.columns(3)
    c1.metric("Permeat", f"{ergebnisse['total_permeat']:.1f} l/h")
    c2.metric("Konzentrat", f"{ergebnisse['end_konzentrat_flow']:.1f} l/h")
    c3.metric("Permeat TDS", f"{ergebnisse['total_permeat_tds']:.1f} ppm")
    st.dataframe(pd.DataFrame(ergebnisse['membran_daten']))
