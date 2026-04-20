import streamlit as st
import math

st.set_page_config(page_title="Profi RO-Simulator", layout="wide")

st.title("🌊 Erweiterter RO-Anlagen Simulator")

# --- Sidebar: System-Parameter ---
with st.sidebar:
    st.header("System-Einstellungen")
    temp = st.slider("Wassertemperatur (°C)", 10, 50, 15)
    zuleitung = st.selectbox("Zuleitung (Zoll)", ["1/2", "1", "2"], index=1)
    anzahl_membranen = st.number_input("Anzahl Membranen", 1, 10, 1)
    ausbeute_pct = st.slider("Ausbeute (WCF %)", 10, 90, 50)
    
    st.header("Wasser-Qualität")
    p_pumpen_druck = st.number_input("Pumpendruck (bar)", 1.0, 70.0, 15.0)
    tds_feed = st.number_input("Feed TDS (ppm)", 50, 10000, 500)

# --- Hauptbereich: Membraneigenschaften (Dropdown/Expander) ---
with st.expander("🛠️ Spezifische Membraneigenschaften (Datenblatt-Werte)"):
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        m_flaeche = st.number_input("Aktive Filterfläche (m²)", value=7.5, help="Datenblatt: Active Area")
        m_test_flow = st.number_input("Test-Permeatfluss (m³/h)", value=0.38, help="Datenblatt: Permeate Flow Rate")
    with col_m2:
        m_test_druck = st.number_input("Test-Druck (bar)", value=15.5, help="Druck, bei dem der Test-Flow gemessen wurde")
        m_test_tds = st.number_input("Test-TDS (ppm)", value=1500, help="TDS-Wert im Datenblatt-Test")
    m_rueckhalt = st.slider("Salzrückhalt (%)", 90.0, 99.9, 99.0) / 100.0

# --- Physikalische Berechnungen ---

# 1. Temperatur-Korrektur-Faktor (TCF)
# Standard-Formel für Standard-Polyamid-Membranen
tcf = math.exp(2640 * (1/298.15 - 1/(temp + 273.15)))

# 2. Permeabilität (A-Wert) aus Datenblatt berechnen
pi_test = (m_test_tds / 100) * 0.07 # Osmotischer Druck beim Test
ndp_test = m_test_druck - pi_test
# A-Wert = Fluss / (Fläche * NDP)
a_wert = m_test_flow / (m_flaeche * ndp_test)

# 3. Aktuelle Berechnung
pi_real = (tds_feed / 100) * 0.07
ndp_real = p_pumpen_druck - pi_real

if ndp_real <= 0:
    st.error("Der Pumpendruck reicht nicht aus, um den osmotischen Druck zu überwinden!")
else:
    # Gesamtleistung unter Berücksichtigung von Anzahl, Temperatur und A-Wert
    q_permeat = (anzahl_membranen * m_flaeche) * a_wert * ndp_real * tcf
    
    q_feed = q_permeat / (ausbeute_pct / 100.0)
    q_konzentrat = q_feed - q_permeat
    
    tds_permeat = tds_feed * (1 - m_rueckhalt)
    tds_konzentrat = ((q_feed * tds_feed) - (q_permeat * tds_permeat)) / q_konzentrat

    # --- Ergebnis-Anzeige ---
    st.divider()
    res_col1, res_col2, res_col3 = st.columns(3)
    
    res_col1.metric("Permeatfluss", f"{q_permeat:.2f} m³/h", help="Berücksichtigt Temperatur und Membranalterung (theoretisch)")
    res_col1.metric("TDS Permeat", f"{tds_permeat:.1f} ppm")
    
    res_col2.metric("Konzentratfluss", f"{q_konzentrat:.2f} m³/h")
    res_col2.metric("TDS Konzentrat", f"{tds_konzentrat:.0f} ppm")
    
    res_col3.metric("TCF Faktor", f"{tcf:.2f}", help="Verhältnis der Leistung zu 25°C Referenztemperatur")
    res_col3.metric("Speisestrom", f"{q_feed:.2f} m³/h")

    # --- Warnungen ---
    st.subheader("Anlagen-Check")
    rohr_limits = {"1/2": 1.5, "1": 3.5, "2": 14.0}
    if q_feed > rohr_limits[zuleitung]:
        st.warning(f"⚠️ Speisestrom zu hoch für {zuleitung}\" Rohrleitung!")
    else:
        st.success(f"✅ Hydraulik innerhalb der Limits für {zuleitung}\" Anschluss.")
