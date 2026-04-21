import streamlit as st
import pandas as pd
import math

# --- EIGENE MODULE IMPORTIEREN ---
from hydraulik.widerstand import berechne_hydraulischen_widerstand, r_parallel
from system.reihe import simuliere_reihe
from system.parallel import simuliere_parallel

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")
st.title("💧 RO-Anlagen Planer & Hydraulik-Netzwerk")

# --- SIDEBAR ---
with st.sidebar:
    with st.expander("1. Verschaltung & Aufbau", expanded=True):
        schaltung = st.selectbox("Verschaltung", ["In Reihe (Konzentrat -> Feed)", "Parallel (Aufteilung)"])
        
        # Dynamische Membrananzahl je nach Modus
        if schaltung == "In Reihe (Konzentrat -> Feed)":
            anzahl_membranen = st.number_input("Anzahl Membranen", 1, 10, 2)
        else:
            st.info("💡 Die Anzahl der Membranen wird automatisch anhand deiner Rohr-Abzweigungen (Sektion 3) berechnet.")
            anzahl_membranen = 1 # Platzhalter, wird gleich dynamisch überschrieben
            
        ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 90, 50)
    
    with st.expander("2. Membrane & System", expanded=False):
        m_flaeche = st.number_input("Filterfläche (m²)", value=7.5)
        m_test_flow = st.number_input("Nennleistung (l/h)", value=380.0)
        m_test_druck = st.number_input("Test-Druck (bar)", value=15.5)
        m_rueckhalt = st.slider("Rückhalt (%)", 90.0, 99.9, 99.2) / 100
        st.divider()
        tds_feed = st.number_input("Feed TDS (ppm)", value=500)
        temp = st.slider("Temperatur (°C)", 10, 50, 15)
        p_system = st.number_input("Systemdruck nach Pumpe (bar)", value=15.0)

    with st.expander("3. Rohrleitungen Zuleitung", expanded=False):
        st.markdown("**Saugseite (Vor Pumpe)**")
        d_saug = st.number_input("Ø Innen Saugseite (mm)", value=20.0, key="ds")
        l_saug = st.number_input("Länge (mm)", value=1000.0, key="ls")
        b_saug = st.number_input("Anzahl 90° Bögen", 0, 10, 0, key="bs")
        n_drossel_saug = st.number_input("Anzahl Drosseln", 0, 5, 0, key="nds")
        drosseln_saug = [st.number_input(f"Ø Drossel {i+1} (mm)", value=10.0, key=f"drs_{i}") for i in range(n_drossel_saug)]
        r_saug = berechne_hydraulischen_widerstand(d_saug, l_saug, drosseln_saug, b_saug)
        
        st.divider()
        st.markdown("**Druckseite Hauptleitung**")
        d_druck = st.number_input("Ø Hauptleitung (mm)", value=15.0)
        l_druck = st.number_input("Länge Hauptleitung (mm)", value=2000.0)
        b_druck = st.number_input("Bögen Hauptleitung", 0, 10, 0)
        r_druck_haupt = berechne_hydraulischen_widerstand(d_druck, l_druck, [], b_druck)
        
        r_netzwerk = 0
        hat_t_stueck, sub_a, sub_b = False, False, False
        flow_fractions = [1.0]
        membran_namen = ["Modul 1 (Haupt)"]
        
        if schaltung == "Parallel (Aufteilung)":
            hat_t_stueck = st.checkbox("Hauptleitung durch T-Stück aufteilen")
            if hat_t_stueck:
                # --- STRANG A ---
                st.markdown("#### Strang A")
                ca1, ca2, ca3 = st.columns(3)
                d_a, l_a, b_a = ca1.number_input("Ø Strang A", 15.0), ca2.number_input("Länge A", 1000.0), ca3.number_input("Bögen A", 0)
                
                sub_a = st.checkbox("↳ Strang A in A1 & A2 aufteilen")
                if sub_a:
                    st.caption("Unterstrang A1")
                    cA1_1, cA1_2, cA1_3 = st.columns(3)
                    d_a1, l_a1, b_a1 = cA1_1.number_input("Ø A1", 10.0), cA1_2.number_input("Länge A1", 500.0), cA1_3.number_input("Bögen A1", 0)
                    
                    st.caption("Unterstrang A2")
                    cA2_1, cA2_2, cA2_3 = st.columns(3)
                    d_a2, l_a2, b_a2 = cA2_1.number_input("Ø A2", 10.0), cA2_2.number_input("Länge A2", 500.0), cA2_3.number_input("Bögen A2", 0)
                    
                    r_a1 = berechne_hydraulischen_widerstand(d_a1, l_a1, [], b_a1)
                    r_a2 = berechne_hydraulischen_widerstand(d_a2, l_a2, [], b_a2)
                    r_a_sub = r_parallel(r_a1, r_a2)
                else: r_a_sub, r_a1, r_a2 = 0, 0, 0
                r_a_tot = berechne_hydraulischen_widerstand(d_a, l_a, [], b_a) + r_a_sub

                # --- STRANG B ---
                st.markdown("#### Strang B")
                cb1, cb2, cb3 = st.columns(3)
                d_b, l_b, b_b = cb1.number_input("Ø Strang B", 15.0), cb2.number_input("Länge B", 1000.0), cb3.number_input("Bögen B", 0)
                
                sub_b = st.checkbox("↳ Strang B in B1 & B2 aufteilen")
                if sub_b:
                    st.caption("Unterstrang B1")
                    cB1_1, cB1_2, cB1_3 = st.columns(3)
                    d_b1, l_b1, b_b1 = cB1_1.number_input("Ø B1", 10.0), cB1_2.number_input("Länge B1", 500.0), cB1_3.number_input("Bögen B1", 0)
                    
                    st.caption("Unterstrang B2")
                    cB2_1, cB2_2, cB2_3 = st.columns(3)
                    d_b2, l_b2, b_b2 = cB2_1.number_input("Ø B2", 10.0), cB2_2.number_input("Länge B2", 500.0), cB2_3.number_input("Bögen B2", 0)
                    
                    r_b1 = berechne_hydraulischen_widerstand(d_b1, l_b1, [], b_b1)
                    r_b2 = berechne_hydraulischen_widerstand(d_b2, l_b2, [], b_b2)
                    r_b_sub = r_parallel(r_b1, r_b2)
                else: r_b_sub, r_b1, r_b2 = 0, 0, 0
                r_b_tot = berechne_hydraulischen_widerstand(d_b, l_b, [], b_b) + r_b_sub
                
                r_netzwerk = r_parallel(r_a_tot, r_b_tot)

                # --- PHYSIKALISCHE FLUSS-BERECHNUNG ---
                pct_a = math.sqrt(r_b_tot) / (math.sqrt(r_a_tot) + math.sqrt(r_b_tot)) if (r_a_tot + r_b_tot) > 0 else 0.5
                pct_b = 1.0 - pct_a
                
                pct_a1 = math.sqrt(r_a2) / (math.sqrt(r_a1) + math.sqrt(r_a2)) if sub_a and (r_a1 + r_a2) > 0 else 1.0
                pct_b1 = math.sqrt(r_b2) / (math.sqrt(r_b1) + math.sqrt(r_b2)) if sub_b and (r_b1 + r_b2) > 0 else 1.0

                # --- NAMENS & STRANG MAPPING ---
                if sub_a and sub_b:
                    anzahl_membranen = 4
                    flow_fractions = [pct_a * pct_a1, pct_a * (1 - pct_a1), pct_b * pct_b1, pct_b * (1 - pct_b1)]
                    membran_namen = ["Modul 1 (A1)", "Modul 2 (A2)", "Modul 3 (B1)", "Modul 4 (B2)"]
                elif sub_a and not sub_b:
                    anzahl_membranen = 3
                    flow_fractions = [pct_a * pct_a1, pct_a * (1 - pct_a1), pct_b]
                    membran_namen = ["Modul 1 (A1)", "Modul 2 (A2)", "Modul 3 (B)"]
                elif not sub_a and sub_b:
                    anzahl_membranen = 3
                    flow_fractions = [pct_a, pct_b * pct_b1, pct_b * (1 - pct_b1)]
                    membran_namen = ["Modul 1 (A)", "Modul 2 (B1)", "Modul 3 (B2)"]
                else:
                    anzahl_membranen = 2
                    flow_fractions = [pct_a, pct_b]
                    membran_namen = ["Modul 1 (A)", "Modul 2 (B)"]

                st.divider()
                st.success(f"**Live Balancing:**\nStrang A: {pct_a*100:.1f}% | Strang B: {pct_b*100:.1f}%")

    with st.expander("4. Konzentrat- & Zwischenleitungen", expanded=False):
        leitungen_konz = []
        leitung_out = None
        if schaltung == "In Reihe (Konzentrat -> Feed)":
            for i in range(anzahl_membranen - 1):
                leitungen_konz.append({
                    "d": st.number_input(f"Ø Innen {i+1}->{i+2}", value=15.0, key=f"d_k_{i}"),
                    "l": st.number_input(f"Länge {i+1}->{i+2}", value=500.0, key=f"l_k_{i}"),
                    "b": st.number_input(f"Bögen {i+1}->{i+2}", 0, 10, 2, key=f"b_k_{i}")
                })
            leitung_out = {
                "d": st.number_input("Ø Innen Auslass (mm)", value=15.0, key="d_out"),
                "l": st.number_input("Länge Auslass (mm)", value=1000.0, key="l_out"),
                "b": st.number_input("Bögen Auslass", 0, 10, 2, key="b_out")
            }
        else:
            for i in range(anzahl_membranen - 1):
                leitungen_konz.append({
                    "d": st.number_input(f"Ø Sammel {i+1}", value=20.0, key=f"d_p_{i}"),
                    "l": st.number_input(f"Länge Sammel {i+1}", value=300.0, key=f"l_p_{i}"),
                    "b": st.number_input(f"Bögen Sammel {i+1}", 0, 10, 0, key=f"b_p_{i}")
                })

# --- BERECHNUNG ---
if schaltung == "In Reihe (Konzentrat -> Feed)":
    ergebnisse = simuliere_reihe(anzahl_membranen, ausbeute_pct, m_flaeche, m_test_flow, m_test_druck, m_rueckhalt, tds_feed, temp, p_system, r_saug, r_druck_haupt, leitungen_konz, leitung_out)
else:
    ergebnisse = simuliere_parallel(flow_fractions, membran_namen, ausbeute_pct, m_flaeche, m_test_flow, m_test_druck, m_rueckhalt, tds_feed, temp, p_system, r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, leitungen_konz)

if ergebnisse.get("error"):
    st.error(ergebnisse["error"])
    st.stop()

# --- UI OUTPUT ---
st.subheader("📊 Anlagen-Performance")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Gesamt Permeat", f"{ergebnisse['total_permeat']:.1f} l/h")
c2.metric("Gesamt Konzentrat", f"{ergebnisse['end_konzentrat_flow']:.1f} l/h")
c3.metric("Benötigter Speisestrom", f"{ergebnisse['q_feed_start_lh']:.1f} l/h")
c4.metric("Ist-Ausbeute", f"{(ergebnisse['total_permeat'] / ergebnisse['q_feed_start_lh'] * 100):.1f} %" if ergebnisse['q_feed_start_lh'] > 0 else "0 %")

q1, q2, q3 = st.columns(3)
q1.metric("Feed TDS (Eingang)", f"{tds_feed:.0f} ppm")
q2.metric("Permeat TDS (Gesamt)", f"{ergebnisse['total_permeat_tds']:.1f} ppm")
q3.metric("Konzentrat TDS (Abfluss)", f"{ergebnisse['final_konzentrat_tds']:.0f} ppm")

st.dataframe(pd.DataFrame(ergebnisse['membran_daten']), use_container_width=True)

st.subheader("🔧 Hydraulik-Analyse")
h1, h2 = st.columns(2)
with h1: st.info(f"Druckverlust Saugseite: **{ergebnisse['p_verlust_saug']:.3f} bar**")
with h2: 
    st.write(f"- Verlust Hauptleitung: {ergebnisse['p_verlust_druck_haupt']:.3f} bar")
    if hat_t_stueck and schaltung == "Parallel (Aufteilung)":
       st.write(f"- Verlust im Split-Netzwerk: {ergebnisse['p_verlust_netzwerk']:.3f} bar")
    st.success(f"Effektiver Druck an Anlage: **{ergebnisse['p_effektiv_start']:.2f} bar**")

st.divider()
st.subheader("🛑 Konzentrat-Regelventil (End-Drossel)")
v1, v2, v3 = st.columns(3)
v1.metric("Restdruck vor Ventil", f"{ergebnisse['konzentrat_druck_verlauf']:.2f} bar")
v2.metric("Abzubauender Druck (ΔP)", f"{ergebnisse['abzubauender_druck']:.2f} bar")
v3.metric("Empfohlener Drossel Ø", f"Ø {ergebnisse['empfohlene_drossel_mm']:.2f} mm")
