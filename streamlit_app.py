import streamlit as st
import math
import pandas as pd

st.set_page_config(page_title="RO-Anlagen Planer Profi", layout="wide")
st.title("💧 RO-Anlagen Planer & Hydraulik-Netzwerk")

# --- Kernfunktionen ---
def berechne_hydraulischen_widerstand(d_inner_mm, laenge_mm, drosseln_liste, anzahl_90_grad, zeta_extra=0.0):
    if d_inner_mm <= 0: return 1e12
    d_m = d_inner_mm / 1000
    area = math.pi * (d_m/2)**2
    zeta_rohr = 0.03 * (laenge_mm/1000 / d_m)
    zeta_drossel = sum([1.5 * (d_inner_mm/d)**4 for d in drosseln_liste if d > 0])
    zeta_bogen = anzahl_90_grad * 1.2
    return (zeta_rohr + zeta_drossel + zeta_bogen + zeta_extra) * 500 / (area**2)

def empfehle_drossel_durchmesser(flow_lh, delta_p_bar):
    if flow_lh <= 0 or delta_p_bar <= 0: return 0.0
    q_ms = (flow_lh / 1000) / 3600
    delta_p_pa = delta_p_bar * 100000
    v_spalt = math.sqrt((2 * delta_p_pa) / (2.5 * 1000))
    d_m = math.sqrt((4 * (q_ms / v_spalt)) / math.pi)
    return d_m * 1000 

# --- SIDEBAR: KONFIGURATION ---
with st.sidebar:
    st.header("1. Grundkonfiguration")
    schaltung = st.selectbox("Verschaltung", ["In Reihe (Konzentrat -> Feed)", "Parallel (Aufteilung)"])
    anzahl_membranen = st.number_input("Anzahl Membranen", 1, 10, 2)
    ausbeute_pct = st.slider("Ziel-Ausbeute (%)", 5, 90, 50)
    
    with st.expander("Membran-Eigenschaften"):
        m_flaeche = st.number_input("Filterfläche (m²)", value=7.5)
        m_test_flow = st.number_input("Nennleistung (l/h)", value=380.0)
        m_test_druck = st.number_input("Test-Druck (bar)", value=15.5)
        m_rueckhalt = st.slider("Rückhalt (%)", 90.0, 99.9, 99.2) / 100
        
    tds_feed = st.number_input("Feed TDS (ppm)", value=500)
    temp = st.slider("Temperatur (°C)", 10, 50, 15)
    p_system = st.number_input("Pumpendruck (bar)", value=15.0)

    st.header("2. Hydraulik Zuleitung")
    with st.expander("Zuleitung ZUR Pumpe (Saugseite)"):
        d_saug = st.number_input("Ø Innen (mm)", 20.0, key="ds")
        l_saug = st.number_input("Länge (mm)", 1000.0, key="ls")
        b_saug = st.number_input("Bögen", 0, 10, 0, key="bs")
        dr_saug = [st.number_input("Drossel Ø (mm)", 0.0, key="drs")]
    
    with st.expander("Zuleitung NACH Pumpe (Druckseite)"):
        d_druck = st.number_input("Ø Hauptleitung (mm)", 15.0)
        l_druck = st.number_input("Länge Hauptleitung (mm)", 2000.0)
        b_druck = st.number_input("Bögen Hauptleitung", 0, 10, 0)
        dr_druck = [st.number_input("Drossel Ø (mm)", 0.0)]
        hat_t_stueck = (schaltung == "Parallel") and st.checkbox("T-Stück Aufteilung aktiv")
        if hat_t_stueck:
            st.info("Balancing aktiv: Leitung A/B werden symmetrisch berechnet.")

    st.header("3. Konzentrat-Leitungen")
    leitungen_konz = []
    if schaltung == "In Reihe (Konzentrat -> Feed)":
        for i in range(anzahl_membranen - 1):
            with st.expander(f"Zischenleitung: Membran {i+1} -> {i+2}"):
                leitungen_konz.append({
                    "d": st.number_input("Ø", value=15.0, key=f"d_k_{i}"),
                    "l": st.number_input("L", value=500.0, key=f"l_k_{i}"),
                    "b": st.number_input("B", 0, 10, 2, key=f"b_k_{i}"),
                    "dr": st.number_input("Drossel Ø", 0.0, key=f"dr_k_{i}")
                })
        with st.expander("Konzentrat-Auslassleitung (Ende)", expanded=True):
            leitung_out = {"d": st.number_input("Ø Auslass", 15.0), "l": st.number_input("L Auslass", 1000.0), "b": st.number_input("Bögen", 0, 10, 2)}
    else:
        for i in range(anzahl_membranen):
            with st.expander(f"Konzentratleitung Membran {i+1} -> Mischleitung"):
                leitungen_konz.append({
                    "d": st.number_input("Ø", value=15.0, key=f"d_p_{i}"),
                    "l": st.number_input("L", value=500.0, key=f"l_p_{i}"),
                    "b": st.number_input("B", 0, 10, 0, key=f"b_p_{i}"),
                    "dr": st.number_input("Drossel Ø", 0.0, key=f"dr_p_{i}")
                })
        with st.expander("Mischleitung nach Zusammenfluss", expanded=True):
            leitung_out = {"d": st.number_input("Ø Misch", 20.0), "l": st.number_input("L Misch", 1000.0), "b": st.number_input("Bögen", 0, 10, 2)}

# --- BERECHNUNGS-LOGIK ---
tcf = math.exp(2640 * (1/298.15 - 1/(temp + 273.15)))
a_wert = (m_test_flow/1000) / (m_flaeche * (m_test_druck - (1500/100*0.07)))

# Initialer Feed-Bedarf
ndp_start = p_system - (tds_feed/100*0.07)
q_feed = (anzahl_membranen * m_flaeche * a_wert * max(0, ndp_start) * tcf * 1000) / (ausbeute_pct/100)

# Druckverluste (P = R * Q^2)
r_s = berechne_hydraulischen_widerstand(d_saug, l_saug, dr_saug, b_saug)
r_d = berechne_hydraulischen_widerstand(d_druck, l_druck, dr_druck, b_druck)
p_eff = p_system - (r_d * ((q_feed/1000)/3600)**2)/100000

membran_daten = []
current_p = p_eff
current_feed = q_feed
total_permeat = 0

for i in range(anzahl_membranen):
    p_in = current_p
    f_in = current_feed / (anzahl_membranen if schaltung == "Parallel" else 1)
    
    q_p = m_flaeche * a_wert * max(0, p_in - (tds_feed/100*0.07)) * tcf * 1000
    q_c = f_in - q_p
    
    membran_daten.append({"Modul": i+1, "P_in (bar)": round(p_in, 2), "Permeat (l/h)": round(q_p, 1), "Konzentrat (l/h)": round(q_c, 1)})
    total_permeat += q_p
    
    if schaltung == "In Reihe (Konzentrat -> Feed)" and i < anzahl_membranen - 1:
        cfg = leitungen_konz[i]
        r = berechne_hydraulischen_widerstand(cfg['d'], cfg['l'], [cfg['dr']], cfg['b'])
        current_p = (p_in - 0.2) - (r * ((q_c/1000)/3600)**2)/100000
        current_feed = q_c

# Enddrossel-Check
flow_out = q_feed - total_permeat
r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
p_out = (r_out * ((flow_out/1000)/3600)**2)/100000
d_drossel = empfehle_drossel_durchmesser(max(1, flow_out), max(0.1, current_p - p_out - 0.5))

# --- OUTPUT ---
st.subheader("📊 Berechnungsergebnisse")
st.dataframe(pd.DataFrame(membran_daten), use_container_width=True)

c1, c2, c3 = st.columns(3)
c1.metric("Gesamt Permeat", f"{total_permeat:.1f} l/h")
c2.metric("Ist-Ausbeute", f"{(total_permeat/q_feed*100):.1f} %")
c3.metric("Empfohlener Drosseldurchmesser", f"{d_drossel:.2f} mm")
