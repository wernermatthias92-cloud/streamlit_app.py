import streamlit as st
import pandas as pd
import math

from hydraulik.widerstand import berechne_hydraulischen_widerstand, r_parallel
from system.reihe import simuliere_reihe
from system.parallel import simuliere_parallel

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")
st.title("💧 RO-Anlagen Planer & Hydraulik-Netzwerk")

with st.sidebar:
    with st.expander("1. Verschaltung & Aufbau", expanded=True):
        schaltung = st.selectbox("Verschaltung", ["Parallel (Aufteilung)", "In Reihe (Konzentrat -> Feed)"])
        if schaltung == "In Reihe (Konzentrat -> Feed)":
            anzahl_membranen = st.number_input("Anzahl Membranen", 1, 10, 2)
        else:
            st.info("💡 Membran-Anzahl wird dynamisch aus Sektion 3 berechnet.")
            anzahl_membranen = 1 
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
        d_saug = st.number_input("Ø Innen Saugseite (mm)", value=20.0, key="ds")
        l_saug = st.number_input("Länge (mm)", min_value=1.0, value=1000.0, step=10.0, key="ls")
        b_saug = st.number_input("Anzahl 90° Bögen", 0, 10, 0, key="bs")
        n_drossel_saug = st.number_input("Anzahl Drosseln", 0, 5, 0, key="nds")
        drosseln_saug = [st.number_input(f"Ø Drossel {i+1} (mm)", value=10.0, key=f"drs_{i}") for i in range(n_drossel_saug)]
        r_saug = berechne_hydraulischen_widerstand(d_saug, l_saug, drosseln_saug, b_saug)
        st.divider()
        d_druck = st.number_input("Ø Hauptleitung (mm)", value=15.0)
        l_druck = st.number_input("Länge Hauptleitung (mm)", min_value=1.0, value=2000.0, step=10.0)
        b_druck = st.number_input("Bögen Hauptleitung", 0, 10, 0)
        r_druck_haupt = berechne_hydraulischen_widerstand(d_druck, l_druck, [], b_druck)
        r_netzwerk = 0
        hat_t_stueck, sub_a, sub_b = False, False, False
        flow_fractions, membran_namen = [1.0], ["Modul 1 (Haupt)"]
        
        if schaltung == "Parallel (Aufteilung)":
            hat_t_stueck = st.checkbox("Hauptleitung durch T-Stück aufteilen")
            if hat_t_stueck:
                st.markdown("#### Strang A")
                d_a, l_a, b_a = st.number_input("Ø A", 15.0), st.number_input("Länge A", 1000.0, min_value=1.0), st.number_input("Bögen A", 0)
                sub_a = st.checkbox("↳ A aufteilen")
                r_a_sub = 0
                if sub_a:
                    r_a1 = berechne_hydraulischen_widerstand(st.number_input("Ø A1", 10.0), st.number_input("Länge A1", 500.0, min_value=1.0), [], st.number_input("Bögen A1", 0))
                    r_a2 = berechne_hydraulischen_widerstand(st.number_input("Ø A2", 10.0), st.number_input("Länge A2", 500.0, min_value=1.0), [], st.number_input("Bögen A2", 0))
                    r_a_sub = r_parallel(r_a1, r_a2)
                r_a_tot = berechne_hydraulischen_widerstand(d_a, l_a, [], b_a) + r_a_sub
                st.markdown("#### Strang B")
                d_b, l_b, b_b = st.number_input("Ø B", 15.0), st.number_input("Länge B", 1000.0, min_value=1.0), st.number_input("Bögen B", 0)
                sub_b = st.checkbox("↳ B aufteilen")
                r_b_sub = 0
                if sub_b:
                    r_b1 = berechne_hydraulischen_widerstand(st.number_input("Ø B1", 10.0), st.number_input("Länge B1", 500.0, min_value=1.0), [], st.number_input("Bögen B1", 0))
                    r_b2 = berechne_hydraulischen_widerstand(st.number_input("Ø B2", 10.0), st.number_input("Länge B2", 500.0, min_value=1.0), [], st.number_input("Bögen B2", 0))
                    r_b_sub = r_parallel(r_b1, r_b2)
                r_b_tot = berechne_hydraulischen_widerstand(d_b, l_b, [], b_b) + r_b_sub
                r_netzwerk = r_parallel(r_a_tot, r_b_tot)
                # Mapping (vereinfacht für UI-Platz)
                pct_a = math.sqrt(r_b_tot)/(math.sqrt(r_a_tot)+math.sqrt(r_b_tot)) if (r_a_tot+r_b_tot)>0 else 0.5
                if sub_a and sub_b: flow_fractions, membran_namen = [pct_a*0.5, pct_a*0.5, (1-pct_a)*0.5, (1-pct_a)*0.5], ["A1","A2","B1","B2"]
                elif sub_a: flow_fractions, membran_namen = [pct_a*0.5, pct_a*0.5, 1-pct_a], ["A1","A2","B"]
                elif sub_b: flow_fractions, membran_namen = [pct_a, (1-pct_a)*0.5, (1-pct_a)*0.5], ["A","B1","B2"]
                else: flow_fractions, membran_namen = [pct_a, 1-pct_a], ["A","B"]
                anzahl_membranen = len(flow_fractions)

    with st.expander("4. Konzentratleitungen", expanded=False):
        leitungen_konz, leitung_out = [], None
        if schaltung == "Parallel (Aufteilung)":
            if anzahl_membranen == 1:
                leitung_out = {"d": st.number_input("Ø Auslass (mm)", 15.0), "l": st.number_input("Länge Auslass", 1000.0, min_value=1.0), "b": st.number_input("Bögen Auslass", 2)}
            else:
                for i in range(anzahl_membranen):
                    leitungen_konz.append({"d": st.number_input(f"Ø {membran_namen[i]}->T", 15.0), "l": st.number_input(f"Länge {membran_namen[i]}", 500.0, min_value=1.0), "b": st.number_input(f"Bögen {membran_namen[i]}", 0)})
                leitung_out = {"d": st.number_input("Ø T->Drossel", 20.0), "l": st.number_input("Länge T->Drossel", 1000.0, min_value=1.0), "b": st.number_input("Bögen T->Drossel", 2)}

    with st.expander("5. Permeatleitungen", expanded=False):
        p_leitungen_konz, p_leitung_out = [], None
        if schaltung == "Parallel (Aufteilung)":
            if anzahl_membranen == 1:
                st.markdown("**Permeatleitung bis Anlagenausgang**")
                p_leitung_out = {"d": st.number_input("Ø Permeat (mm)", 10.0), "l": st.number_input("Länge (mm)", 2000.0, min_value=1.0), "b": st.number_input("Bögen", 0)}
            else:
                for i in range(anzahl_membranen):
                    p_leitungen_konz.append({"d": st.number_input(f"Ø {membran_namen[i]}->T (P)", 10.0, key=f"pd{i}"), "l": st.number_input(f"Länge {membran_namen[i]} (P)", 500.0, min_value=1.0, key=f"pl{i}"), "b": st.number_input(f"Bögen {membran_namen[i]} (P)", 0, key=f"pb{i}")})
                st.divider()
                p_leitung_out = {"d": st.number_input("Ø Sammelrohr (P)", 15.0), "l": st.number_input("Länge Sammel (P)", 2000.0, min_value=1.0), "b": st.number_input("Bögen Sammel (P)", 0)}

# --- BERECHNUNG ---
if schaltung == "In Reihe (Konzentrat -> Feed)":
    ergebnisse = simuliere_reihe(anzahl_membranen, ausbeute_pct, m_flaeche, m_test_flow, m_test_druck, m_rueckhalt, tds_feed, temp, p_system, r_saug, r_druck_haupt, [], {"d":15,"l":1000,"b":2}) # Dummy out
else:
    ergebnisse = simuliere_parallel(flow_fractions, membran_namen, ausbeute_pct, m_flaeche, m_test_flow, m_test_druck, m_rueckhalt, tds_feed, temp, p_system, r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, leitungen_konz, leitung_out, p_leitungen_konz, p_leitung_out)

if ergebnisse.get("error"):
    st.error(ergebnisse["error"])
    st.stop()

# --- UI OUTPUT ---
st.subheader("📊 Performance")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Gesamt Permeat", f"{ergebnisse['total_permeat']:.1f} l/h")
c2.metric("Gesamt Konzentrat", f"{ergebnisse['end_konzentrat_flow']:.1f} l/h")
c3.metric("Permeat TDS", f"{ergebnisse['total_permeat_tds']:.1f} ppm")
c4.metric("Konz. TDS", f"{ergebnisse['final_konzentrat_tds']:.0f} ppm")

st.dataframe(pd.DataFrame(ergebnisse['membran_daten']), use_container_width=True)
st.divider()
st.subheader("🛑 Drossel & Hydraulik")
v1, v2, v3 = st.columns(3)
v1.metric("P vor Ventil", f"{ergebnisse['konzentrat_druck_verlauf']:.2f} bar")
v2.metric("ΔP Drossel", f"{ergebnisse['abzubauender_druck']:.2f} bar")
v3.metric("Drossel Ø", f"Ø {ergebnisse['empfohlene_drossel_mm']:.2f} mm")
