import streamlit as st

# Seiteneinstellungen
st.set_page_config(page_title="RO-Anlagen Simulator", layout="centered")

st.title("💧 RO-Anlagen Simulator (4040)")
st.write("Berechnung der theoretischen Volumenströme und TDS-Werte.")

# --- Sidebar für Einstellungen ---
st.sidebar.header("Anlagen-Parameter")

zuleitung = st.sidebar.selectbox("Zuleitung (Zoll)", ["1/2", "1", "2"], index=1)
anzahl_membranen = st.sidebar.slider("Anzahl Membranen (4040)", 1, 5, 1)
ausbeute_prozent = st.sidebar.slider("Gewünschte Ausbeute (WCF %)", 10, 90, 50)

st.sidebar.header("Wasser-Parameter")
p_feed = st.sidebar.number_input("Eingangsdruck (bar)", min_value=1.0, max_value=40.0, value=15.0)
tds_feed = st.sidebar.number_input("Eingangswasser TDS (ppm)", min_value=50, max_value=5000, value=500)

# --- Konstanten ---
FLAECHE_PRO_MEMBRAN = 7.5  # m²
SALZRUECKHALT = 0.99
PERMEABILITAET_A = 0.035
ROHR_LIMITS = {"1/2": 1.5, "1": 3.5, "2": 14.0}

# --- Berechnung ---
wcf = ausbeute_prozent / 100.0
p_osmotisch = (tds_feed / 100) * 0.07
ndp = p_feed - p_osmotisch

if ndp <= 0:
    st.error("FEHLER: Der Eingangsdruck ist zu niedrig, um den osmotischen Druck zu überwinden!")
else:
    # Volumenströme
    q_permeat = anzahl_membranen * FLAECHE_PRO_MEMBRAN * PERMEABILITAET_A * ndp
    q_feed = q_permeat / wcf
    q_konzentrat = q_feed - q_permeat

    # TDS Werte
    tds_permeat = tds_feed * (1 - SALZRUECKHALT)
    tds_konzentrat = ((q_feed * tds_feed) - (q_permeat * tds_permeat)) / q_konzentrat

    # --- Anzeige ---
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Permeatstrom", f"{q_permeat:.2f} m³/h")
        st.metric("TDS Permeat", f"{tds_permeat:.1f} ppm")
    with col2:
        st.metric("Konzentratstrom", f"{q_konzentrat:.2f} m³/h")
        st.metric("TDS Konzentrat", f"{tds_konzentrat:.1f} ppm")

    st.subheader("System-Check")
    st.write(f"Erforderlicher Speisestrom: **{q_feed:.2f} m³/h**")
    
    # Rohrleitungs-Warnung
    max_rohr = ROHR_LIMITS[zuleitung]
    if q_feed > max_rohr:
        st.warning(f"⚠️ ACHTUNG: Der Speisestrom überschreitet das Limit der {zuleitung}\" Leitung ({max_rohr} m³/h)!")
    else:
        st.success(f"✅ Die {zuleitung}\" Leitung ist ausreichend dimensioniert.")

    st.info(f"Der osmotische Druck des Speisewassers beträgt ca. {p_osmotisch:.2f} bar.")
