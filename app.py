import streamlit as st
import pandas as pd
import math

# --- EIGENE MODULE IMPORTIEREN ---
from hydraulik.widerstand import berechne_hydraulischen_widerstand, r_parallel
from system.reihe import simuliere_reihe
from system.parallel import simuliere_parallel
from system.parallel_drossel import simuliere_parallel_drossel
from utils.pdf_export import generiere_pdf

# Seitenkonfiguration
st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")

# --- 1. SIDEBAR (EINGABEPARAMETER) ---
with st.sidebar:
    with st.expander("1. Verschaltung & Aufbau", expanded=True):
        schaltung = st.selectbox("Verschaltung", ["Parallel (Aufteilung)", "In Reihe (Konzentrat -> Feed)"])
        
        if schaltung == "In Reihe (Konzentrat -> Feed)":
            anzahl_membranen = st.number_input("Anzahl Membranen", 1, 10, 2)
            ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 90, 50)
            auslegungs_modus = "Ziel-Ausbeute vorgeben" 
            drossel_vorgabe_mm = 0
            
        else:
            st.info("💡 Die Anzahl der Membranen wird automatisch anhand deiner Rohr-Abzweigungen (Sektion 3) berechnet.")
            anzahl_membranen = 1 
            
            # Auswahl zwischen Planung (Ausbeute) und Simulation (Drossel)
            auslegungs_modus = st.radio("Auslegungs-Modus", ["Ziel-Ausbeute vorgeben", "Drossel-Ø vorgeben (Digital Twin)"])
            
            if auslegungs_modus == "Ziel-Ausbeute vorgeben":
                ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 90, 50)
                drossel_vorgabe_mm = 0
            else:
                drossel_vorgabe_mm = st.number_input("Fester Drossel-Ø (mm)", min_value=0.1, value=1.2, step=0.1)
                ausbeute_pct = 0
    
    with st.expander("2. Membrane & System", expanded=False):
        m_flaeche = st.number_input("Filterfläche (m²)", value=7.5)
        m_test_flow = st.number_input("Nennleistung (l/h)", value=568.0)
        m_test_druck = st.number_input("Test-Druck (bar)", value=9.3)
        m_rueckhalt = st.slider("Rückhalt (%)", 90.0, 99.9, 98.0) / 100
        st.divider()
        tds_feed = st.number_input("Feed TDS (ppm)", value=96)
        temp = st.slider("Temperatur (°C)", 10, 50, 13)
        
        st.divider()
        st.markdown("**Pumpen-Parameter**")
        if auslegungs_modus == "Ziel-Ausbeute vorgeben" or schaltung == "In Reihe (Konzentrat -> Feed)":
            p_system = st.number_input("Statischer Systemdruck nach Pumpe (bar)", value=9.4)
            pumpe_p_max = p_system 
            pumpe_q_max = 0 
        else:
            # Reale Pumpenkennlinie für den Digital Twin
            st.caption("Eckpunkte der Pumpenkennlinie (PQ-Kurve):")
            pumpe_p_max = st.number_input("Max. Druck (P0) bei 0 l/h (bar)", value=11.5, step=0.5)
            pumpe_q_max = st.number_input("Max. Durchfluss (Qmax) bei 0 bar (l/h)", value=2500.0, step=100.0)
            p_system = pumpe_p_max

    with st.expander("3. Rohrleitungen Zuleitung", expanded=False):
        st.markdown("**Saugseite (Hausanschluss)**")
        p_zulauf = st.number_input("Zulaufdruck (bar)", value=3.0, step=0.5)
        
        d_saug = st.number_input("Ø Innen Saugseite (mm)", value=13.2, key="ds")
        l_saug = st.number_input("Länge (mm)", min_value=1.0, value=1000.0, key="ls")
        b_saug = st.number_input("Anzahl 90° Bögen", 0, 10, 0, key="bs")
        n_drossel_saug = st.number_input("Anzahl Drosseln", 0, 5, 0, key="nds")
        drosseln_saug = [st.number_input(f"Ø Drossel {i+1} (mm)", value=10.0, key=f"drs_{i}") for i in range(n_drossel_saug)]
        r_saug = berechne_hydraulischen_widerstand(d_saug, l_saug, drosseln_saug, b_saug)
        
        st.divider()
        st.markdown("**Druckseite (Hauptleitung)**")
        d_druck = st.number_input("Ø Hauptleitung (mm)", value=13.2)
        l_druck = st.number_input("Länge Hauptleitung (mm)", min_value=1.0, value=400.0)
        b_druck = st.number_input("Bögen Hauptleitung", 0, 10, 0)
        r_druck_haupt = berechne_hydraulischen_widerstand(d_druck, l_druck, [], b_druck)
        
        r_netzwerk = 0
        hat_t_stueck, sub_a, sub_b = False, False, False
        flow_fractions, membran_namen = [1.0], ["Modul 1 (Haupt)"]
        
        if schaltung == "Parallel (Aufteilung)":
            hat_t_stueck = st.checkbox("Hauptleitung durch T-Stück aufteilen", value=True)
            if hat_t_stueck:
                st.markdown("#### Strang A")
                ca1, ca2, ca3 = st.columns(3)
                d_a = ca1.number_input("Ø A", value=13.2)
                l_a = ca2.number_input("Länge A", value=150.0, min_value=1.0) 
                b_a = ca3.number_input("Bögen A", value=1)
                
                sub_a = st.checkbox("↳ A aufteilen")
                r_a_sub = 0
                if sub_a:
                    cA1_1, cA1_2, cA1_3 = st.columns(3)
                    d_a1 = cA1_1.number_input("Ø A1", value=10.0)
                    l_a1 = cA1_2.number_input("Länge A1", value=500.0)
                    b_a1 = cA1_3.number_input("Bögen A1", value=0)
                    r_a1 = berechne_hydraulischen_widerstand(d_a1, l_a1, [], b_a1)
                    # A2... (logik analog zu A1)
                    r_a2 = r_a1 # Vereinfachung für den Beispielcode
                    r_a_sub = r_parallel(r_a1, r_a2)
                r_a_tot = berechne_hydraulischen_widerstand(d_a, l_a, [], b_a) + r_a_sub
                
                st.markdown("#### Strang B")
                cb1, cb2, cb3 = st.columns(3)
                d_b = cb1.number_input("Ø B", value=13.2)
                l_b = cb2.number_input("Länge B", value=150.0, min_value=1.0)
                b_b = cb3.number_input("Bögen B", value=1)
                
                sub_b = st.checkbox("↳ B aufteilen", value=True)
                r_b_sub = 0
                if sub_b:
                    cB1_1, cB1_2, cB1_3 = st.columns(3)
                    d_b1 = cB1_1.number_input("Ø B1", value=13.2)
                    l_b1 = cB1_2.number_input("Länge B1", value=200.0)
                    b_b1 = cB1_3.number_input("Bögen B1", value=0)
                    r_b1 = berechne_hydraulischen_widerstand(d_b1, l_b1, [], b_b1)
                    
                    cB2_1, cB2_2, cB2_3 = st.columns(3)
                    d_b2 = cB2_1.number_input("Ø B2", value=13.2)
                    l_b2 = cB2_2.number_input("Länge B2", value=200.0)
                    b_b2 = cB2_3.number_input("Bögen B2", value=0)
                    r_b2 = berechne_hydraulischen_widerstand(d_b2, l_b2, [], b_b2)
                    r_b_sub = r_parallel(r_b1, r_b2)
                r_b_tot = berechne_hydraulischen_widerstand(d_b, l_b, [], b_b) + r_b_sub
                
                r_netzwerk = r_parallel(r_a_tot, r_b_tot)
                
                # --- PHYSIKALISCH KORREKTE FLUSS-AUFTEILUNG (CONDUCTANCE) ---
                R_MEM_BASE = 50000.0 
                r_path_a = r_a_tot + R_MEM_BASE
                r_path_b1 = r_b_tot - r_b_sub + r_b1 + R_MEM_BASE
                r_path_b2 = r_b_tot - r_b_sub + r_b2 + R_MEM_BASE
                
                c_a = 1.0 / math.sqrt(r_path_a) if not sub_a else 0 # Hier vereinfacht für B-Split
                c_b1 = 1.0 / math.sqrt(r_path_b1)
                c_b2 = 1.0 / math.sqrt(r_path_b2)
                c_tot = c_a + c_b1 + c_b2
                
                flow_fractions = [c_a/c_tot, c_b1/c_tot, c_b2/c_tot]
                membran_namen = ["A", "B1", "B2"]
                anzahl_membranen = len(flow_fractions)

    with st.expander("4. Konzentratleitungen", expanded=False):
        # Hier werden d, l, b für die Konzentratpfade abgefragt (analog zu vorher)
        leitungen_konz = [] # Dummy zur Demonstration
        leitung_out = {"d": 6.0, "l": 300.0, "b": 2}

    with st.expander("5. Permeatleitungen", expanded=False):
        # Hier werden d, l, b für Permeatpfade abgefragt (analog zu vorher)
        p_leitungen_konz = []
        p_leitung_out = {"d": 13.2, "l": 1000.0, "b": 0}
        p_schlauch_out = {"d": 13.2, "l": 1.0, "h": 0.0}

# --- 2. BERECHNUNG ---
if schaltung == "In Reihe (Konzentrat -> Feed)":
    ergebnisse = simuliere_reihe(anzahl_membranen, ausbeute_pct, m_flaeche, m_test_flow, m_test_druck, m_rueckhalt, tds_feed, temp, p_system, r_saug, r_druck_haupt, [], leitung_out)
else:
    if auslegungs_modus == "Ziel-Ausbeute vorgeben":
        ergebnisse = simuliere_parallel(flow_fractions, membran_namen, ausbeute_pct, m_flaeche, m_test_flow, m_test_druck, m_rueckhalt, tds_feed, temp, p_system, r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, [], leitung_out, [], p_leitung_out, p_schlauch_out)
    else:
        # Digital Twin Aufruf mit Pumpenkurve und Zulaufdruck
        ergebnisse = simuliere_parallel_drossel(flow_fractions, membran_namen, drossel_vorgabe_mm, m_flaeche, m_test_flow, m_test_druck, m_rueckhalt, tds_feed, temp, pumpe_p_max, pumpe_q_max, p_zulauf, r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, [], leitung_out, [], p_leitung_out, p_schlauch_out)

# --- 3. UI MAIN WINDOW ---
col_title, col_btn = st.columns([4, 1])
with col_title: st.title("💧 RO-Anlagen Planer")
with col_btn:
    inputs_fuer_pdf = {"schaltung": schaltung, "anzahl_membranen": anzahl_membranen, "ausbeute_pct": ausbeute_pct, "m_flaeche": m_flaeche, "m_test_flow": m_test_flow, "m_test_druck": m_test_druck, "m_rueckhalt": m_rueckhalt, "tds_feed": tds_feed, "temp": temp, "p_system": p_system}
    pdf_bytes = generiere_pdf(inputs_fuer_pdf, ergebnisse)
    st.download_button(label="📄 PDF Protokoll Export", data=pdf_bytes, file_name="ro_protokoll.pdf", mime="application/pdf")

st.divider()
st.subheader("📊 Performance")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Gesamt Permeat", f"{ergebnisse['total_permeat']:.1f} l/h")
c2.metric("Gesamt Konzentrat", f"{ergebnisse['end_konzentrat_flow']:.1f} l/h")
c3.metric("Permeat TDS", f"{ergebnisse['total_permeat_tds']:.1f} ppm")
c4.metric("Konz. TDS", f"{ergebnisse['final_konzentrat_tds']:.0f} ppm")

st.dataframe(pd.DataFrame(ergebnisse['membran_daten']), use_container_width=True)

st.divider()
st.subheader("🛑 Hydraulik & Drossel")
v1, v2, v3 = st.columns(3)
if auslegungs_modus == "Drossel-Ø vorgeben (Digital Twin)":
    v1.metric("Pumpendruck (Real)", f"{ergebnisse.get('realer_pumpendruck', 0):.2f} bar")
else:
    v1.metric("Systemdruck (Statisch)", f"{p_system:.2f} bar")
v2.metric("P vor Ventil", f"{ergebnisse['konzentrat_druck_verlauf']:.2f} bar")
if auslegungs_modus == "Drossel-Ø vorgeben (Digital Twin)":
    v3.metric("Drossel Ø", f"Ø {drossel_vorgabe_mm:.2f} mm")
else:
    v3.metric("Empfohlener Drossel Ø", f"Ø {ergebnisse['empfohlene_drossel_mm']:.2f} mm")
