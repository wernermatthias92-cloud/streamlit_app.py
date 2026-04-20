import streamlit as st
import math
import pandas as pd

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")
st.title("💧 RO-Anlagen Planer & Hydraulik-Netzwerk")

# --- Kernfunktionen ---
def berechne_hydraulischen_widerstand(d_inner_mm, laenge_mm, drosseln_liste, anzahl_90_grad, zeta_extra=0.0):
    if d_inner_mm <= 0: return 1e12
    d_m = d_inner_mm / 1000
    area = math.pi * (d_m/2)**2
    zeta_rohr = 0.03 * (laenge_mm/1000 / d_m)
    zeta_drossel = sum([1.5 * (d_inner_mm/d)**4 for d in drosseln_liste if d > 0])
    zeta_bogen = anzahl_90_grad * 1.2
    zeta_total = zeta_rohr + zeta_drossel + zeta_bogen + zeta_extra
    return zeta_total * 500 / (area**2)

def empfehle_drossel_durchmesser(flow_lh, delta_p_bar):
    if flow_lh <= 0 or delta_p_bar <= 0: return 0.0
    q_ms = (flow_lh / 1000) / 3600
    delta_p_pa = delta_p_bar * 100000
    v_spalt = math.sqrt((2 * delta_p_pa) / (2.5 * 1000))
    d_m = math.sqrt((4 * (q_ms / v_spalt)) / math.pi)
    return d_m * 1000 

# --- SIDEBAR (Menüs) ---
with st.sidebar:
    st.header("Anlagen-Konfiguration")
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
    p_system = st.number_input("Systemdruck nach Pumpe (bar)", value=15.0)

    # Zuleitungs-Menüs
    with st.expander("Leitung ZUR Pumpe"):
        d_saug = st.number_input("Ø Saug (mm)", value=20.0)
        l_saug = st.number_input("L Saug (mm)", value=1000.0)
        b_saug = st.number_input("Bögen Saug", 0, 10, 0)
        dr_saug = [st.number_input("Drossel Saug (mm)", value=0.0)]
    
    with st.expander("Leitung NACH Pumpe"):
        d_druck = st.number_input("Ø Haupt (mm)", value=15.0)
        l_druck = st.number_input("L Haupt (mm)", value=2000.0)
        hat_t_stueck = (schaltung == "Parallel") and st.checkbox("T-Stück Aufteilung")
    
    # Konzentrat-Menüs
    leitungen_konz = []
    if schaltung == "In Reihe (Konzentrat -> Feed)":
        for i in range(anzahl_membranen - 1):
            with st.expander(f"Zischenleitung {i+1} -> {i+2}"):
                leitungen_konz.append({"d": st.number_input("Ø", value=15.0, key=f"dk{i}"), "l": st.number_input("L", value=500.0, key=f"lk{i}"), "b": st.number_input("B", 0, 10, 0, key=f"bk{i}"), "dr": st.number_input("Dr", value=0.0, key=f"drk{i}")})
        with st.expander("Konzentrat-Auslass", expanded=True):
            leitung_out = {"d": st.number_input("Ø Auslass", value=15.0), "l": st.number_input("L Auslass", value=1000.0), "b": st.number_input("B Auslass", 0, 10, 2)}
    else:
        for i in range(anzahl_membranen):
            with st.expander(f"Konzentratleitung Membran {i+1}"):
                leitungen_konz.append({"d": st.number_input("Ø", value=15.0, key=f"dp{i}"), "l": st.number_input("L", value=500.0, key=f"lp{i}"), "b": st.number_input("B", 0, 10, 0, key=f"bp{i}"), "dr": st.number_input("Dr", value=0.0, key=f"drp{i}")})
        with st.expander("Mischleitung (Auslass)", expanded=True):
            leitung_out = {"d": st.number_input("Ø Misch", value=20.0), "l": st.number_input("L Misch", value=1000.0), "b": st.number_input("B Misch", 0, 10, 2)}

# --- BERECHNUNGS-LOGIK ---
tcf = math.exp(2640 * (1/298.15 - 1/(temp + 273.15)))
a_wert = (m_test_flow/1000) / (m_flaeche * (m_test_druck - (1500/100*0.07)))

# Initialer Flow (Schätzung)
ndp_start = p_system - (tds_feed/100*0.07)
q_feed = (anzahl_membranen * m_flaeche * a_wert * max(0, ndp_start) * tcf * 1000) / (ausbeute_pct/100)

# Hydraulikverluste
r_s = berechne_hydraulischen_widerstand(d_saug, l_saug, dr_saug, b_saug)
r_d = berechne_hydraulischen_widerstand(d_druck, l_druck, [], 0)
p_verlust_s = (r_s * ((q_feed/1000)/3600)**2)/100000
p_verlust_d = (r_d * ((q_feed/1000)/3600)**2)/100000
p_eff = p_system - p_verlust_d

membran_daten = []
total_permeat = 0
current_p = p_eff
current_feed = q_feed

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

# Drossel-Berechnung
r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
flow_out = q_feed - total_permeat
p_out = (r_out * ((flow_out/1000)/3600)**2)/100000
d_drossel = empfehle_drossel_durchmesser(max(1, flow_out), max(0.1, current_p - p_out - 0.5))

# --- UI OUTPUT ---
st.subheader("📊 Berechnungsergebnisse")
st.dataframe(pd.DataFrame(membran_daten))
c1, c2, c3 = st.columns(3)
c1.metric("Gesamt Permeat", f"{total_permeat:.1f} l/h")
c2.metric("Ist-Ausbeute", f"{(total_permeat/q_feed*100):.1f} %")
c3.metric("Empfohlener Drosseldurchmesser", f"{d_drossel:.2f} mm")
