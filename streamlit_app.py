import streamlit as st
import math
import pandas as pd

st.set_page_config(page_title="RO-Anlagen Planer", layout="wide")
st.title("💧 RO-Anlagen Planer & Hydraulik-Check")

# --- Hilfsfunktion für Druckverlust (erweitert) ---
def berechne_druckverlust(flow_lh, d_inner_mm, laenge_mm, drosseln_liste, anzahl_90_grad):
    if d_inner_mm <= 0 or flow_lh <= 0: return 0
    q_ms = (flow_lh / 1000) / 3600  
    d_m = d_inner_mm / 1000
    area = math.pi * (d_m/2)**2
    v = q_ms / area 
    
    rho = 1000 # Dichte Wasser kg/m³
    dyn_druck = rho * v**2 / 2 # Staudruck
    
    # 1. Rohrreibung
    p_verlust_pa = 0.03 * (laenge_mm/1000 / d_m) * dyn_druck
    
    # 2. Drosseln (Zeta ca. 1.5)
    for d_drossel in drosseln_liste:
        if d_drossel > 0:
            p_verlust_pa += 1.5 * dyn_druck * (d_inner_mm / d_drossel)**2
            
    # 3. 90° Bögen (scharf, Zeta ca. 1.2)
    p_verlust_pa += anzahl_90_grad * 1.2 * dyn_druck
            
    return p_verlust_pa / 100000 # Umrechnung in bar

# Hilfsfunktion für lokales T-Stück
def t_stueck_verlust(flow_lh, d_inner_mm):
    if d_inner_mm <= 0 or flow_lh <= 0: return 0
    q_ms = (flow_lh / 1000) / 3600  
    d_m = d_inner_mm / 1000
    v = q_ms / (math.pi * (d_m/2)**2)
    p_verlust_pa = 1.3 * (1000 * v**2 / 2) # Zeta 1.3 für T-Aufteilung
    return p_verlust_pa / 100000

# --- SIDEBAR: PARAMETER ---
with st.sidebar:
    st.header("1. Verschaltung & Aufbau")
    schaltung = st.selectbox("Verschaltung der Membranen", ["In Reihe (Konzentrat -> Feed)", "Parallel (Aufteilung)"])
    anzahl_membranen = st.number_input("Anzahl Membranen", 1, 10, 3)
    ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (WCF %)", 5, 90, 50)
    
    st.header("2. Membraneigenschaften")
    with st.expander("Details anpassen", expanded=False):
        m_flaeche = st.number_input("Filterfläche (m²)", value=7.5)
        m_test_flow = st.number_input("Nennleistung (l/h)", value=380.0)
        m_test_druck = st.number_input("Test-Druck (bar)", value=15.5)
        m_test_tds = st.number_input("Test-TDS (ppm)", value=1500)
        m_rueckhalt = st.slider("Rückhalt (%)", 90.0, 99.9, 99.2) / 100

    st.header("3. Wasser & System")
    temp = st.slider("Wassertemperatur (°C)", 10, 50, 15)
    tds_feed = st.number_input("Feed TDS (ppm)", 50, 10000, 500)
    p_system = st.number_input("Systemdruck nach Pumpe (bar)", 1.0, 70.0, 15.0)

    st.header("4. Hydraulik & Leitungen")
    
    # SAUGSEITE
    with st.expander("Leitung ZUR Pumpe (Saugseite)"):
        d_saug = st.number_input("Ø Innen (mm)", value=20.0, key="ds")
        l_saug = st.number_input("Länge (mm)", value=1000.0, key="ls")
        bogen_saug = st.number_input("Anzahl 90° Bögen", 0, 20, 0, key="bs")
        n_drossel_saug = st.number_input("Anzahl Drosseln", 0, 5, 0, key="nds")
        drosseln_saug = [st.number_input(f"Ø Drossel {i+1} (mm)", value=10.0, key=f"drs_{i}") for i in range(n_drossel_saug)]

    # DRUCKSEITE HAUPT
    with st.expander("Leitung NACH Pumpe (Druckseite)"):
        d_druck = st.number_input("Ø Innen (mm)", value=15.0, key="dd")
        l_druck = st.number_input("Länge (mm)", value=2000.0, key="ld")
        bogen_druck = st.number_input("Anzahl 90° Bögen", 0, 20, 0, key="bd")
        n_drossel_druck = st.number_input("Anzahl Drosseln", 0, 5, 0, key="ndd")
        drosseln_druck = [st.number_input(f"Ø Drossel {i+1} (mm)", value=8.0, key=f"drd_{i}") for i in range(n_drossel_druck)]
        
        st.divider()
        hat_t_stueck = st.checkbox("T-Stück einbauen (Teilt Strang in A & B)")
        
        # DYNAMISCHE STRÄNGE A & B
        if hat_t_stueck:
            st.markdown("**Strang A (Nach T-Stück)**")
            d_a = st.number_input("Ø Innen A (mm)", value=15.0)
            l_a = st.number_input("Länge A (mm)", value=1000.0)
            bogen_a = st.number_input("Bögen A", 0, 20, 0)
            
            st.markdown("**Strang B (Nach T-Stück)**")
            d_b = st.number_input("Ø Innen B (mm)", value=15.0)
            l_b = st.number_input("Länge B (mm)", value=1000.0)
            bogen_b = st.number_input("Bögen B", 0, 20, 0)

# --- BERECHNUNG ---
tcf = math.exp(2640 * (1/298.15 - 1/(temp + 273.15)))
a_wert = (m_test_flow/1000) / (m_flaeche * (m_test_druck - (m_test_tds/100*0.07)))

pi_real_start = (tds_feed / 100) * 0.07
ndp_start = p_system - pi_real_start
q_p_approx_total = (anzahl_membranen * m_flaeche) * a_wert * max(0, ndp_start) * tcf * 1000

q_feed_start_lh = q_p_approx_total / (ausbeute_pct / 100) if (ausbeute_pct > 0 and q_p_approx_total > 0) else 0

membran_daten = []
total_permeat = 0

if ndp_start <= 0:
    st.error("Systemdruck zu gering, um osmotischen Druck zu überwinden!")
else:
    # Hydraulik Berechnungen
    verlust_saug = berechne_druckverlust(q_feed_start_lh, d_saug, l_saug, drosseln_saug, bogen_saug)
    
    # Druckseite Hauptleitung
    verlust_druck_haupt = berechne_druckverlust(q_feed_start_lh, d_druck, l_druck, drosseln_druck, bogen_druck)
    
    # Abzweige berechnen falls vorhanden
    verlust_druck_gesamt = verlust_druck_haupt
    verlust_t_teil = 0
    verlust_a = 0
    verlust_b = 0
    
    if hat_t_stueck:
        flow_branch = q_feed_start_lh / 2 # Aufteilung 50:50
        verlust_t_teil = t_stueck_verlust(q_feed_start_lh, d_druck)
        verlust_a = berechne_druckverlust(flow_branch, d_a, l_a, [], bogen_a)
        verlust_b = berechne_druckverlust(flow_branch, d_b, l_b, [], bogen_b)
        # Wir nehmen den hydraulisch ungünstigeren Zweig (Maximaler Verlust) als Referenz für die Membranen
        verlust_druck_gesamt += verlust_t_teil + max(verlust_a, verlust_b)

    p_effektiv_start = p_system - verlust_druck_gesamt

    current_feed_flow = q_feed_start_lh
    current_tds = tds_feed
    current_p = p_effektiv_start

    # Membran-Schleife
    for i in range(anzahl_membranen):
        if schaltung == "Parallel":
            f_in = q_feed_start_lh / anzahl_membranen
            p_in = p_effektiv_start 
            tds_in = tds_feed
        else:
            f_in = current_feed_flow
            p_in = current_p
            tds_in = current_tds

        pi = (tds_in / 100) * 0.07
        ndp = max(0, p_in - pi)
        q_p = m_flaeche * a_wert * ndp * tcf * 1000
        if q_p > f_in * 0.95: q_p = f_in * 0.95 
        
        q_c = f_in - q_p
        tds_p = tds_in * (1 - m_rueckhalt)
        tds_c = ((f_in * tds_in) - (q_p * tds_p)) / q_c if q_c > 0 else tds_in
        total_permeat += q_p

        membran_daten.append({
            "Membran": f"Modul {i+1}",
            "Druck Eintritt (bar)": round(p_in, 2),
            "Feed TDS (ppm)": round(tds_in, 0),
            "Speisestrom (l/h)": round(f_in, 1),
            "Permeatstrom (l/h)": round(q_p, 1),
            "Konzentrat (l/h)": round(q_c, 1)
        })

        if schaltung == "In Reihe (Konzentrat -> Feed)":
            current_feed_flow = q_c
            current_tds = tds_c
            current_p = p_in - 0.2

    ist_ausbeute = (total_permeat / q_feed_start_lh) * 100 if q_feed_start_lh > 0 else 0

    # --- UI OUTPUT ---
    st.subheader("📊 Anlagen-Performance")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gesamt Permeat", f"{total_permeat:.1f} l/h")
    c2.metric("Gesamt Konzentrat", f"{(q_feed_start_lh - total_permeat):.1f} l/h")
    c3.metric("Benötigter Speisestrom", f"{q_feed_start_lh:.1f} l/h")
    c4.metric("Ist-Ausbeute", f"{ist_ausbeute:.1f} %")

    with st.expander("🔍 Detail-Werte pro Membran anzeigen"):
        st.dataframe(pd.DataFrame(membran_daten), use_container_width=True)

    st.subheader("🔧 Hydraulik-Analyse Leitungen")
    h1, h2 = st.columns(2)
    with h1:
        st.markdown("**Saugseite (Vor Pumpe)**")
        st.info(f"Druckverlust: **{verlust_saug:.3f} bar**")
        if verlust_saug > 0.3: st.warning("⚠️ Kavitationsgefahr! Saugwiderstand zu hoch.")
    with h2:
        st.markdown("**Druckseite (Pumpe -> Membran)**")
        if hat_t_stueck:
            st.write(f"- Verlust Hauptleitung: {verlust_druck_haupt:.3f} bar")
            st.write(f"- Verlust T-Stück (Split): {verlust_t_teil:.3f} bar")
            st.write(f"- Verlust Strang A: {verlust_a:.3f} bar | Strang B: {verlust_b:.3f} bar")
            st.info(f"Gesamtverlust Druckseite: **{verlust_druck_gesamt:.3f} bar**")
        else:
            st.info(f"Gesamtverlust Druckseite: **{verlust_druck_gesamt:.3f} bar**")
        
        st.success(f"Effektiver Druck an Anlage: **{p_effektiv_start:.2f} bar**")
