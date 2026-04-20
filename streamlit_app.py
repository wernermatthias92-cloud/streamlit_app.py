import streamlit as st
import math

st.set_page_config(page_title="RO-Anlagen Planer", layout="wide")

st.title("💧 RO-Anlagen Planer & Hydraulik-Check")

# --- Hilfsfunktion für Druckverlust (vereinfacht) ---
def berechne_druckverlust(flow_lh, d_inner_mm, laenge_mm, drosseln_liste):
    if d_inner_mm <= 0: return 0
    # Umrechnung in SI-Einheiten
    q_ms = (flow_lh / 1000) / 3600  # m³/s
    d_m = d_inner_mm / 1000
    area = math.pi * (d_m/2)**2
    v = q_ms / area # m/s
    
    # Reibungsbeiwert (Lamda) ca. 0.03 für glatte Schläuche
    rho = 1000 # kg/m³
    p_verlust_pa = 0.03 * (laenge_mm/1000 / d_m) * (rho * v**2 / 2)
    
    # Drosselverluste (Zeta ca. 1.5 pro Verengung als Schätzwert)
    for d_drossel in drosseln_liste:
        if d_drossel > 0:
            # Verhältnis-basierter Zeta-Wert
            p_verlust_pa += 1.5 * (rho * v**2 / 2) * (d_inner_mm / d_drossel)**2
            
    return p_verlust_pa / 100000 # bar

# --- SIDEBAR: PARAMETER ---
with st.sidebar:
    st.header("1. Membraneigenschaften")
    with st.expander("Details anpassen", expanded=False):
        m_flaeche = st.number_input("Filterfläche (m²)", value=7.5)
        m_test_flow = st.number_input("Nennleistung (l/h)", value=380.0)
        m_test_druck = st.number_input("Test-Druck (bar)", value=15.5)
        m_test_tds = st.number_input("Test-TDS (ppm)", value=1500)
        m_rueckhalt = st.slider("Rückhalt (%)", 90.0, 99.9, 99.2) / 100

    st.header("2. Anlagen-Setup")
    anzahl_membranen = st.number_input("Anzahl Membranen", 1, 10, 1)
    ausbeute_pct = st.slider("Ausbeute (WCF %)", 5, 90, 50)
    temp = st.slider("Wassertemperatur (°C)", 10, 50, 15)
    tds_feed = st.number_input("Feed TDS (ppm)", 50, 10000, 500)
    p_system = st.number_input("Systemdruck nach Pumpe (bar)", 1.0, 70.0, 15.0)

    st.header("3. Hydraulik & Schläuche")
    # Saugseite
    with st.expander("Schlauchleitung ZUR Pumpe"):
        d_saug = st.number_input("Ø Innen Saugseite (mm)", value=20.0)
        l_saug = st.number_input("Länge Saugseite (mm)", value=1000.0)
        n_drossel_saug = st.number_input("Anzahl Drosseln (Saug)", 0, 5, 0)
        drosseln_saug = []
        for i in range(n_drossel_saug):
            drosseln_saug.append(st.number_input(f"Ø Drossel {i+1} (Saug mm)", value=10.0))

    # Druckseite
    with st.expander("Schlauchleitung ZUR Membrane"):
        d_druck = st.number_input("Ø Innen Druckseite (mm)", value=15.0)
        l_druck = st.number_input("Länge Druckseite (mm)", value=2000.0)
        n_drossel_druck = st.number_input("Anzahl Drosseln (Druck)", 0, 5, 0)
        drosseln_druck = []
        for i in range(n_drossel_druck):
            drosseln_druck.append(st.number_input(f"Ø Drossel {i+1} (Druck mm)", value=8.0))

# --- BERECHNUNG ---
# TCF & A-Wert
tcf = math.exp(2640 * (1/298.15 - 1/(temp + 273.15)))
a_wert = (m_test_flow/1000) / (m_flaeche * (m_test_druck - (m_test_tds/100*0.07)))

# Effektiver Druck am Eintritt der Membrane
# Wir ziehen den Verlust der Druckleitung vom eingestellten Pumpendruck ab
# Da der Fluss unbekannt ist, nutzen wir eine Iteration oder eine Schätzung für die Verluste
# Für dieses Tool nehmen wir an: p_system ist der Druck direkt nach der Pumpe.

pi_real = (tds_feed / 100) * 0.07
ndp = p_system - pi_real

if ndp <= 0:
    st.error("Systemdruck zu gering!")
else:
    q_permeat_lh = (anzahl_membranen * m_flaeche) * a_wert * ndp * tcf * 1000
    q_feed_lh = q_permeat_lh / (ausbeute_pct / 100)
    
    # Jetzt berechnen wir die realen Verluste basierend auf dem Feed-Fluss
    verlust_saug = berechne_druckverlust(q_feed_lh, d_saug, l_saug, drosseln_saug)
    verlust_druck = berechne_druckverlust(q_feed_lh, d_druck, l_druck, drosseln_druck)
    
    p_effektiv_membrane = p_system - verlust_druck

    # --- UI OUTPUT ---
    st.subheader("📊 Performance-Ergebnisse")
    c1, c2, c3 = st.columns(3)
    c1.metric("Permeatfluss", f"{q_permeat_lh:.1f} l/h")
    c2.metric("Konzentratfluss", f"{(q_feed_lh - q_permeat_lh):.1f} l/h")
    c3.metric("Speisewasserbedarf", f"{q_feed_lh:.1f} l/h")

    st.subheader("🔧 Hydraulik-Analyse")
    h1, h2 = st.columns(2)
    with h1:
        st.write("**Saugseite (Vor Pumpe):**")
        st.info(f"Druckverlust: {verlust_saug:.3f} bar")
        if verlust_saug > 0.3: st.warning("⚠️ Kavitationsgefahr! Saugwiderstand zu hoch.")
    with h2:
        st.write("**Druckseite (Pumpe -> Membran):**")
        st.info(f"Druckverlust: {verlust_druck:.3f} bar")
        st.write(f"Effektiver Druck an Membrane: **{p_effektiv_membrane:.2f} bar**")

    st.caption(f"Referenz: Ein Permeatfluss von {q_permeat_lh:.1f} l/h entspricht {(q_permeat_lh/1500)*100:.1f}% der maximal erwarteten 1500 l/h.")
