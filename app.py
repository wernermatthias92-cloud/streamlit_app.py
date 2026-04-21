import streamlit as st
import pandas as pd
import math

# --- EIGENE MODULE IMPORTIEREN ---
# Wir importieren die Hydraulik-Grundfunktionen und die neuen Simulations-Module
from hydraulik.widerstand import berechne_hydraulischen_widerstand, r_parallel
from system.reihe import simuliere_reihe
from system.parallel import simuliere_parallel

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")
st.title("💧 RO-Anlagen Planer & Hydraulik-Netzwerk")

# --- SIDEBAR (Benutzereingaben) ---
with st.sidebar:
    st.header("1. Verschaltung & Aufbau")
    schaltung = st.selectbox("Verschaltung", ["In Reihe (Konzentrat -> Feed)", "Parallel (Aufteilung)"])
    anzahl_membranen = st.number_input("Anzahl Membranen", 1, 10, 2)
    ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 90, 50)
    
    st.header("2. Membrane & System")
    with st.expander("Details anpassen"):
        m_flaeche = st.number_input("Filterfläche (m²)", value=7.5)
        m_test_flow = st.number_input("Nennleistung (l/h)", value=380.0)
        m_test_druck = st.number_input("Test-Druck (bar)", value=15.5)
        m_rueckhalt = st.slider("Rückhalt (%)", 90.0, 99.9, 99.2) / 100
        
    tds_feed = st.number_input("Feed TDS (ppm)", value=500)
    temp = st.slider("Temperatur (°C)", 10, 50, 15)
    p_system = st.number_input("Systemdruck nach Pumpe (bar)", value=15.0)

    st.header("3. Rohrleitungen Zuleitung")
    
    # --- MENÜ 1: Saugseite (Vor der Pumpe) ---
    with st.expander("Zuleitung ZUR Pumpe (Saugseite)", expanded=False):
        d_saug = st.number_input("Ø Innen Saugseite (mm)", value=20.0, key="ds")
        l_saug = st.number_input("Länge (mm)", value=1000.0, key="ls")
        b_saug = st.number_input("Anzahl 90° Bögen", 0, 10, 0, key="bs")
        n_drossel_saug = st.number_input("Anzahl Drosseln", 0, 5, 0, key="nds")
        drosseln_saug = [st.number_input(f"Ø Drossel {i+1} (mm)", value=10.0, key=f"drs_{i}") for i in range(n_drossel_saug)]
    
    r_saug = berechne_hydraulischen_widerstand(d_saug, l_saug, drosseln_saug, b_saug)

    # --- MENÜ 2: Druckseite (Nach der Pumpe) ---
    with st.expander("Zuleitung NACH Pumpe (Druckseite)", expanded=False):
        d_druck = st.number_input("Ø Hauptleitung (mm)", value=15.0)
        l_druck = st.number_input("Länge Hauptleitung (mm)", value=2000.0)
        b_druck = st.number_input("Bögen Hauptleitung", 0, 10, 0)
        r_druck_haupt = berechne_hydraulischen_widerstand(d_druck, l_druck, [], b_druck)
        
        r_netzwerk = 0
        hat_t_stueck = False
        
        # Die T-Stück Logik ist nur für die parallele Aufteilung relevant
        if schaltung == "Parallel (Aufteilung)":
            hat_t_stueck = st.checkbox("Hauptleitung durch T-Stück aufteilen")
            if hat_t_stueck:
                st.markdown("#### Strang A")
                colA1, colA2 = st.columns(2)
                d_a = colA1.number_input("Ø Strang A", value=15.0)
                l_a = colA2.number_input("Länge A", value=1000.0)
                sub_a = st.checkbox("↳ Strang A in A1 & A2 aufteilen")
                if sub_a:
                    cA1, cA2 = st.columns(2)
                    d_a1, l_a1 = cA1.number_input("Ø A1", 10.0), cA1.number_input("Länge A1", 500.0)
                    d_a2, l_a2 = cA2.number_input("Ø A2", 10.0), cA2.number_input("Länge A2", 500.0)
                    r_a_sub = r_parallel(berechne_hydraulischen_widerstand(d_a1, l_a1, [], 0), 
                                         berechne_hydraulischen_widerstand(d_a2, l_a2, [], 0))
                else: r_a_sub = 0
                r_a_tot = berechne_hydraulischen_widerstand(d_a, l_a, [], 0) + r_a_sub

                st.markdown("#### Strang B")
                colB1, colB2 = st.columns(2)
                d_b = colB1.number_input("Ø Strang B", value=15.0)
                l_b = colB2.number_input("Länge B", value=1000.0)
                sub_b = st.checkbox("↳ Strang B in B1 & B2 aufteilen")
                if sub_b:
                    cB1, cB2 = st.columns(2)
                    d_b1, l_b1 = cB1.number_input("Ø B1", 10.0), cB1.number_input("Länge B1", 500.0)
                    d_b2, l_b2 = cB2.number_input("Ø B2", 10.0), cB2.number_input("Länge B2", 500.0)
                    r_b_sub = r_parallel(berechne_hydraulischen_widerstand(d_b1, l_b1, [], 0), 
                                         berechne_hydraulischen_widerstand(d_b2, l_b2, [], 0))
                else: r_b_sub = 0
                r_b_tot = berechne_hydraulischen_widerstand(d_b, l_b, [], 0) + r_b_sub

                r_netzwerk = r_parallel(r_a_tot, r_b_tot)

    st.header("4. Konzentrat- & Zwischenleitungen")
    leitungen_konz = []
    leitung_out = None
    
    if schaltung == "In Reihe (Konzentrat -> Feed)":
        for i in range(anzahl_membranen - 1):
            with st.expander(f"Zwischenleitung: Membran {i+1} -> {i+2}"):
               leitungen_konz.append({
                   "d": st.number_input(f"Ø Innen (mm)", value=15.0, key=f"d_k_{i}"),
                    "l": st.number_input(f"Länge (mm)", value=500.0, key=f"l_k_{i}"),
                    "b": st.number_input(f"Bögen", 0, 10, 2, key=f"b_k_{i}")
                })
        with st.expander(f"Konzentrat-Auslassleitung (nach Membran {anzahl_membranen})", expanded=True):
           leitung_out = {
                "d": st.number_input("Ø Innen Auslass (mm)", value=15.0, key="d_out"),
                "l": st.number_input("Länge Auslass (mm)", value=1000.0, key="l_out"),
                "b": st.number_input("Bögen Auslass", 0, 10, 2, key="b_out")
            }
    else:
        for i in range(anzahl_membranen - 1):
            with st.expander(f"Sammelleitung T-Stück {i+1} (Mischung)"):
               leitungen_konz.append({
                   "d": st.number_input(f"Ø Innen (mm)", value=20.0, key=f"d_p_{i}"),
                    "l": st.number_input(f"Länge (mm)", value=300.0, key=f"l_p_{i}"),
                    "b": st.number_input(f"Bögen", 0, 10, 0, key=f"b_p_{i}")
                })

# --- BERECHNUNG (Routing zu den Modulen) ---
if schaltung == "In Reihe (Konzentrat -> Feed)":
    ergebnisse = simuliere_reihe(
        anzahl_membranen, ausbeute_pct, m_flaeche, m_test_flow,
        m_test_druck, m_rueckhalt, tds_feed, temp, p_system,
        r_saug, r_druck_haupt, leitungen_konz, leitung_out
    )
else:
    ergebnisse = simuliere_parallel(
        anzahl_membranen, ausbeute_pct, m_flaeche, m_test_flow,
        m_test_druck, m_rueckhalt, tds_feed, temp, p_system,
        r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, leitungen_konz
    )

# --- UI OUTPUT ---
if ergebnisse.get("error"):
    st.error(ergebnisse["error"])
    st.stop()

st.subheader("📊 Anlagen-Performance")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Gesamt Permeat", f"{ergebnisse['total_permeat']:.1f} l/h")
c2.metric("Gesamt Konzentrat", f"{ergebnisse['end_konzentrat_flow']:.1f} l/h")
c3.metric("Benötigter Speisestrom", f"{ergebnisse['q_feed_start_lh']:.1f} l/h")
c4.metric("Ist-Ausbeute", f"{(ergebnisse['total_permeat'] / ergebnisse['q_feed_start_lh'] * 100):.1f} %" if ergebnisse['q_feed_start_lh'] > 0 else "0 %")

st.dataframe(pd.DataFrame(ergebnisse['membran_daten']), use_container_width=True)

st.subheader("🔧 Hydraulik-Analyse")
h1, h2 = st.columns(2)
with h1:
    st.info(f"Druckverlust Saugseite: **{ergebnisse['p_verlust_saug']:.3f} bar**")
with h2:
    st.success(f"Effektiver Druck an Anlage: **{ergebnisse['p_effektiv_start']:.2f} bar**")

st.divider()
st.subheader("🛑 Konzentrat-Regelventil (End-Drossel)")
v1, v2, v3 = st.columns(3)
v1.metric("Restdruck vor Ventil", f"{ergebnisse['konzentrat_druck_verlauf']:.2f} bar")
v2.metric("Abzubauender Druck (ΔP)", f"{ergebnisse['abzubauender_druck']:.2f} bar")
v3.metric("Empfohlener Drossel Ø", f"Ø {ergebnisse['empfohlene_drossel_mm']:.2f} mm")
