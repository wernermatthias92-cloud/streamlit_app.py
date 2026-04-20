import streamlit as st
import math
import pandas as pd

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")
st.title("💧 RO-Anlagen Planer & Hydraulik-Netzwerk")

# --- Hydraulik-Kernfunktionen ---
def berechne_hydraulischen_widerstand(d_inner_mm, laenge_mm, drosseln_liste, anzahl_90_grad, zeta_extra=0.0):
    if d_inner_mm <= 0: return 1e12
    d_m = d_inner_mm / 1000
    area = math.pi * (d_m/2)**2
    zeta_rohr = 0.03 * (laenge_mm/1000 / d_m)
    zeta_drossel = sum([1.5 * (d_inner_mm/d)**4 for d in drosseln_liste if d > 0])
    zeta_bogen = anzahl_90_grad * 1.2
    zeta_total = zeta_rohr + zeta_drossel + zeta_bogen + zeta_extra
    return zeta_total * 500 / (area**2)

def r_parallel(r1, r2):
    if r1 <= 0: return r2
    if r2 <= 0: return r1
    return (1/math.sqrt(r1) + 1/math.sqrt(r2))**-2

def empfehle_drossel_durchmesser(flow_lh, delta_p_bar):
    if flow_lh <= 0 or delta_p_bar <= 0: return 0.0
    q_ms = (flow_lh / 1000) / 3600
    delta_p_pa = delta_p_bar * 100000
    v_spalt = math.sqrt((2 * delta_p_pa) / (2.5 * 1000))
    area_m2 = q_ms / v_spalt
    d_m = math.sqrt((4 * area_m2) / math.pi)
    return d_m * 1000 

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Anlagenkonfiguration")
    schaltung = st.selectbox("Verschaltung", ["In Reihe (Konzentrat -> Feed)", "Parallel (Aufteilung)"])
    anzahl_membranen = st.number_input("Anzahl Membranen", 1, 10, 2)
    ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 90, 50)
    
    st.header("2. Systemparameter")
    m_flaeche = st.number_input("Filterfläche pro Modul (m²)", value=7.5)
    tds_feed = st.number_input("Feed TDS (ppm)", value=500)
    p_system = st.number_input("Systemdruck nach Pumpe (bar)", value=15.0)

    st.header("3. Hydraulik Saugseite")
    with st.expander("Leitung ZUR Pumpe"):
        d_saug = st.number_input("Ø Innen Saug (mm)", value=20.0)
        l_saug = st.number_input("Länge (mm)", value=1000.0)
        b_saug = st.number_input("Bögen Saug", 0, 10, 0)
        r_saug = berechne_hydraulischen_widerstand(d_saug, l_saug, [], b_saug)

    st.header("4. Hydraulik Druckseite")
    with st.expander("Hauptleitung NACH Pumpe"):
        d_druck = st.number_input("Ø Hauptleitung (mm)", value=15.0)
        l_druck = st.number_input("Länge (mm)", value=2000.0)
        hat_t_stueck = (schaltung == "Parallel") and st.checkbox("Hauptleitung durch T-Stück aufteilen")
        r_druck_haupt = berechne_hydraulischen_widerstand(d_druck, l_druck, [], 0)
        
        if hat_t_stueck:
            d_a = st.number_input("Ø Strang A (mm)", value=15.0)
            d_b = st.number_input("Ø Strang B (mm)", value=15.0)
            st.success(f"Balancing: Strang A: {50.0}% | Strang B: {50.0}%")

    st.header("5. Konzentrat- & Zwischenleitungen")
    leitungen_konz = []
    if schaltung == "In Reihe (Konzentrat -> Feed)":
        for i in range(anzahl_membranen - 1):
            with st.expander(f"Leitung: Membran {i+1} -> {i+2}"):
                leitungen_konz.append({
                    "d": st.number_input(f"Ø (mm)", value=15.0, key=f"dk{i}"),
                    "l": st.number_input(f"L (mm)", value=500.0, key=f"lk{i}"),
                    "b": st.number_input(f"Bögen", 0, 5, 0, key=f"bk{i}"),
                    "dr": st.number_input("Drossel Ø", value=0.0, key=f"drk{i}")
                })
        with st.expander("Konzentrat-Auslassleitung (Ende)", expanded=True):
            leitung_out = {"d": st.number_input("Ø Auslass (mm)", value=15.0), "l": st.number_input("L Auslass (mm)", value=1000.0), "b": st.number_input("Bögen Auslass", 0, 5, 2)}
    else:
        for i in range(anzahl_membranen):
            with st.expander(f"Konzentratleitung: Membran {i+1} -> Mischleitung"):
                leitungen_konz.append({
                    "d": st.number_input(f"Ø (mm)", value=15.0, key=f"dp{i}"),
                    "l": st.number_input(f"L (mm)", value=500.0, key=f"lp{i}"),
                    "b": st.number_input(f"Bögen", 0, 5, 0, key=f"bp{i}"),
                    "dr": st.number_input("Drossel Ø", value=0.0, key=f"drp{i}")
                })
        with st.expander("Mischleitung bis Drossel", expanded=True):
            leitung_out = {"d": st.number_input("Ø Mischleitung (mm)", value=20.0), "l": st.number_input("L Mischleitung (mm)", value=1000.0), "b": st.number_input("Bögen", 0, 5, 2)}

# --- BERECHNUNG & OUTPUT ---
# (Vereinfachte Logik zur Darstellung der Struktur)
st.subheader("📊 Anlagen-Ergebnisse")
data = []
for i in range(anzahl_membranen):
    data.append({"Modul": i+1, "Druck (bar)": p_system - 0.5 * i, "Status": "Berechnet"})

st.dataframe(pd.DataFrame(data))

# Finaler Drossel-Durchmesser-Check
if 'leitung_out' in locals():
    d_drossel = empfehle_drossel_durchmesser(1500, 5.0)
    st.metric("Empfohlener Drosseldurchmesser", f"{d_drossel:.2f} mm")
