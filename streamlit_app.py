import streamlit as st
import math
import pandas as pd

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")
st.title("💧 RO-Anlagen Planer & Hydraulik-Netzwerk")

# --- Kernfunktionen ---
def berechne_hydraulischen_widerstand(d_inner_mm, laenge_mm, drosseln_liste, anzahl_90_grad, zeta_t_stueck=0.0):
    if d_inner_mm <= 0: return 1e12
    d_m = d_inner_mm / 1000
    area = math.pi * (d_m/2)**2
    zeta_rohr = 0.03 * (laenge_mm/1000 / d_m)
    zeta_drossel = sum([1.5 * (d_inner_mm/d)**4 for d in drosseln_liste if d > 0])
    zeta_bogen = anzahl_90_grad * 1.2
    # T-Stück Umlenkung wird hier als zeta_extra übergeben
    zeta_total = zeta_rohr + zeta_drossel + zeta_bogen + zeta_t_stueck
    return zeta_total * 500 / (area**2)

def empfehle_drossel_durchmesser(flow_lh, delta_p_bar):
    if flow_lh <= 0 or delta_p_bar <= 0: return 0.0
    q_ms = (flow_lh / 1000) / 3600
    delta_p_pa = delta_p_bar * 100000
    v_spalt = math.sqrt((2 * delta_p_pa) / (2.5 * 1000))
    d_m = math.sqrt((4 * (q_ms / v_spalt)) / math.pi)
    return d_m * 1000 

# --- SIDEBAR & MENÜS ---
with st.sidebar:
    st.header("Anlagen-Konfiguration")
    schaltung = st.selectbox("Verschaltung", ["In Reihe (Konzentrat -> Feed)", "Parallel (Aufteilung)"])
    anzahl_membranen = st.number_input("Anzahl Membranen", 1, 10, 2)
    ausbeute_pct = st.slider("Ziel-Ausbeute (%)", 5, 90, 50)
    
    # 1. Saug- & Druckseite (Menüs korrekt getrennt)
    with st.expander("Leitung ZUR Pumpe (Saugseite)"):
        d_saug = st.number_input("Ø Innen (mm)", 20.0, key="ds")
        l_saug = st.number_input("Länge (mm)", 1000.0, key="ls")
        b_saug = st.number_input("Bögen", 0, 10, 0, key="bs")
        dr_saug = [st.number_input("Drossel Ø (mm)", 0.0, key="drs")]
    
    with st.expander("Leitung NACH Pumpe (Druckseite)"):
        d_druck = st.number_input("Ø Haupt (mm)", 15.0)
        l_druck = st.number_input("Länge (mm)", 2000.0)
        dr_druck = [st.number_input("Drossel Ø Haupt (mm)", 0.0)]
        hat_t_stueck = (schaltung == "Parallel") and st.checkbox("T-Stück Hauptleitung aktiv")

    # 2. Konzentratleitungen mit T-Stück-Logik
    leitungen_konz = []
    for i in range(anzahl_membranen if schaltung == "Parallel" else anzahl_membranen - 1):
        name = f"Membran {i+1} -> Mischleitung" if schaltung == "Parallel" else f"Membran {i+1} -> {i+2}"
        with st.expander(name):
            leitungen_konz.append({
                "d": st.number_input("Ø Innen (mm)", 15.0, key=f"d_{i}"),
                "l": st.number_input("Länge (mm)", 500.0, key=f"l_{i}"),
                "b": st.number_input("Bögen", 0, 10, 0, key=f"b_{i}"),
                "dr": st.number_input("Drossel Ø", 0.0, key=f"dr_{i}")
            })
    
    with st.expander("End-Auslass (bis Drossel)", expanded=True):
        leitung_out = {"d": st.number_input("Ø Auslass (mm)", 15.0), "l": st.number_input("L Auslass (mm)", 1000.0), "b": st.number_input("Bögen", 0, 10, 2)}

# --- BERECHNUNG ---
# TCF & A-Wert (Basis 1500ppm)
tcf = math.exp(2640 * (1/298.15 - 1/(temp + 273.15)))
a_val = (380/1000) / (7.5 * (15.5 - (1500/100*0.07)))

# Feed Schätzung
ndp = p_system - (tds_feed/100*0.07)
q_feed = (anzahl_membranen * 7.5 * a_val * max(0, ndp) * tcf * 1000) / (ausbeute_pct/100)

membran_daten = []
current_p = p_system - 0.5 # Vereinfachter Startdruckverlust
current_feed = q_feed

for i in range(anzahl_membranen):
    # Bei Parallel: jedes Modul bekommt Teil-Feed
    f_in = q_feed / anzahl_membranen if schaltung == "Parallel" else current_feed
    p_in = current_p
    
    q_p = 7.5 * a_val * max(0, p_in - (tds_feed/100*0.07)) * tcf * 1000
    q_c = f_in - q_p
    
    # Hier fließt jetzt der T-Stück Widerstand ein!
    zeta = 0.0 if (schaltung == "Parallel" and i == 0) else 1.3
    cfg = leitungen_konz[i]
    r = berechne_hydraulischen_widerstand(cfg['d'], cfg['l'], [cfg['dr']], cfg['b'], zeta_extra=zeta)
    p_verlust = (r * ((q_c/1000)/3600)**2)/100000
    
    membran_daten.append({"Modul": i+1, "P_in (bar)": round(p_in, 2), "Permeat (l/h)": round(q_p, 1), "Konzentrat (l/h)": round(q_c, 1)})
    
    if schaltung == "In Reihe (Konzentrat -> Feed)":
        current_p = (p_in - 0.2) - p_verlust
        current_feed = q_c

# Enddrossel D berechnen
flow_out = q_feed - sum([m["Permeat (l/h)"] for m in membran_daten])
d_drossel = empfehle_drossel_durchmesser(max(1, flow_out), max(0.1, current_p - 0.5))

# --- OUTPUT ---
st.subheader("📊 Berechnungsergebnisse")
st.dataframe(pd.DataFrame(membran_daten), use_container_width=True)
c1, c2 = st.columns(2)
c1.metric("Gesamt Permeat", f"{sum([m['Permeat (l/h)'] for m in membran_daten]):.1f} l/h")
c2.metric("Empfohlener Drosseldurchmesser", f"{d_drossel:.2f} mm")
