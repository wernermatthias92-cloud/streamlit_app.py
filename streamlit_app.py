import streamlit as st
import math
import pandas as pd

st.set_page_config(page_title="RO-Anlagen Planer", layout="wide")
st.title("💧 RO-Anlagen Planer & Hydraulik-Netzwerk")

# --- Funktionen ---
def berechne_r(d, l, drossel_liste, bogen, zeta_extra=0.0):
    if d <= 0: return 1e12
    area = math.pi * (d/2000)**2
    zeta = (0.03 * (l/d)) + sum([1.5 * (d/dr)**4 for dr in drossel_liste if dr > 0]) + (bogen * 1.2) + zeta_extra
    return zeta * 500 / (area**2)

# --- SIDEBAR (Menüs) ---
with st.sidebar:
    st.header("Konfiguration")
    schaltung = st.selectbox("Verschaltung", ["In Reihe", "Parallel"])
    anzahl = st.number_input("Membranen", 1, 10, 2)
    ausbeute = st.slider("Ausbeute (%)", 5, 90, 50) / 100
    
    st.header("Leitungen")
    with st.expander("Zulauf zur Pumpe"):
        d_s, l_s, b_s = st.number_input("Ø (mm)", 20.0), st.number_input("L (mm)", 1000.0), st.number_input("Bögen", 0, 10, 0)
    
    with st.expander("Druckseite (Haupt)"):
        d_d, l_d = st.number_input("Ø (mm)", 15.0), st.number_input("L (mm)", 2000.0)
    
    leitungen_konz = []
    for i in range(anzahl if schaltung == "Parallel" else anzahl - 1):
        with st.expander(f"Konzentrat Leitung {i+1}"):
            leitungen_konz.append({
                "d": st.number_input("Ø", value=15.0, key=f"d{i}"),
                "l": st.number_input("L", value=500.0, key=f"l{i}"),
                "b": st.number_input("B", 0, 10, 0, key=f"b{i}"),
                "dr": st.number_input("Dr", value=0.0, key=f"dr{i}")
            })
    
    with st.expander("Auslassleitung & Ventil"):
        d_out, l_out = st.number_input("Ø Auslass", 15.0), st.number_input("L Auslass", 1000.0)

# --- BERECHNUNG ---
p_system = 15.0 
q_feed = 1500.0 # Annahme für Stabilität
results = []
current_p = p_system

for i in range(anzahl):
    # Zeta 1.3 für T-Stück Umlenkung ab der 2. Membran bei Parallel
    zeta = 1.3 if (schaltung == "Parallel" and i > 0) else 0.0
    
    # Widerstand dieser Teilstrecke
    cfg = leitungen_konz[i] if (schaltung == "Parallel" or i < anzahl - 1) else {"d": d_out, "l": l_out, "b": 2, "dr": 0}
    r = berechne_hydraulischen_widerstand(cfg['d'], cfg['l'], [cfg['dr']], cfg['b'], zeta_extra=zeta)
    
    # Druckabfall
    dp = (r * ((q_feed/anzahl/1000)/3600)**2) / 100000 if schaltung == "Parallel" else 0.2
    current_p -= dp
    
    results.append({"Modul": i+1, "P_in (bar)": round(current_p, 2)})

# --- OUTPUT ---
st.dataframe(pd.DataFrame(results))
st.metric("Drosseldurchmesser (mm)", "4.50") # Placeholder für die finale Berechnung
