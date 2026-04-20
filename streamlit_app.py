import streamlit as st
import math
import pandas as pd

st.set_page_config(page_title="RO-Anlagen Planer (Parallel)", layout="wide")
st.title("💧 RO-Anlagen Planer - Parallelschaltung")

# --- Hydraulik-Kernfunktionen ---
def berechne_hydraulischen_widerstand(d_inner_mm, laenge_mm, drosseln_liste, anzahl_90_grad, zeta_extra=0):
    if d_inner_mm <= 0: return 1e12
    d_m = d_inner_mm / 1000
    area = math.pi * (d_m/2)**2
    
    zeta_rohr = 0.03 * (laenge_mm/1000 / d_m)
    zeta_drossel = sum([1.5 * (d_inner_mm/d)**4 for d in drosseln_liste if d > 0])
    zeta_bogen = anzahl_90_grad * 1.2
    
    # Zeta_extra für T-Stück Umlenkungen
    zeta_total = zeta_rohr + zeta_drossel + zeta_bogen + zeta_extra
    r_wert = zeta_total * 500 / (area**2)
    return r_wert

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
    st.header("1. Aufbau (Parallelschaltung)")
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

    st.header("3. Zuleitungen (Druckseite)")
    with st.expander("Hauptleitung NACH Pumpe", expanded=False):
        d_druck = st.number_input("Ø Hauptleitung (mm)", value=15.0)
        l_druck = st.number_input("Länge Hauptleitung (mm)", value=2000.0)
        b_druck = st.number_input("Bögen Hauptleitung", 0, 10, 0)
        r_druck_haupt = berechne_hydraulischen_widerstand(d_druck, l_druck, [], b_druck)

    st.header("4. Sammelleitungen (Konzentrat)")
    cfg_sammel = {}
    
    if anzahl_membranen == 1:
        with st.expander("Sammelleitung Konzentrat bis Drossel", expanded=True):
            cfg_sammel['d_out'] = st.number_input("Ø Innen (mm)", value=15.0, key="d_s_1")
            cfg_sammel['l_out'] = st.number_input("Länge (mm)", value=1000.0, key="l_s_1")
            cfg_sammel['b_out'] = st.number_input("Bögen", 0, 10, 2, key="b_s_1")
    else:
        with st.expander("Konzentrat Membrane 1 bis Sammelleitung", expanded=True):
            st.caption("Gerader Durchgang am T-Stück (Zeta = 0)")
            cfg_sammel['d_m1'] = st.number_input("Ø Innen (mm)", value=15.0, key="d_m1")
            cfg_sammel['l_m1'] = st.number_input("Länge (mm)", value=500.0, key="l_m1")
            cfg_sammel['b_m1'] = st.number_input("Bögen", 0, 10, 1, key="b_m1")
            
        with st.expander(f"Konzentrat Membrane 2-{anzahl_membranen} bis Sammelleitung"):
            st.caption("Umlenkung im T-Stück (Zeta 1.3 wird addiert)")
            cfg_sammel['d_mn'] = st.number_input("Ø Innen (mm)", value=15.0, key="d_mn")
            cfg_sammel['l_mn'] = st.number_input("Länge (mm)", value=500.0, key="l_mn")
            cfg_sammel['b_mn'] = st.number_input("Bögen", 0, 10, 1, key="b_mn")
            
        with st.expander("Sammelleitung Konzentrat bis Drossel", expanded=True):
            st.caption("Gemeinsames Rohr aller Membranen")
            cfg_sammel['d_out'] = st.number_input("Ø Innen (mm)", value=20.0, key="d_out")
            cfg_sammel['l_out'] = st.number_input("Länge (mm)", value=1000.0, key="l_out")
            cfg_sammel['b_out'] = st.number_input("Bögen", 0, 10, 2, key="b_out")

# --- BERECHNUNG ---
tcf = math.exp(2640 * (1/298.15 - 1/(temp + 273.15)))
a_wert = (m_test_flow/1000) / (m_flaeche * (m_test_druck - (1500/100*0.07)))

ndp_start = p_system - ((tds_feed / 100) * 0.07)
q_p_approx = (anzahl_membranen * m_flaeche) * a_wert * max(0, ndp_start) * tcf * 1000
q_feed_start_lh = q_p_approx / (ausbeute_pct / 100) if (ausbeute_pct > 0 and q_p_approx > 0) else 0

if ndp_start <= 0:
    st.error("Systemdruck zu gering!")
    st.stop()

# Zuleitungsverlust
q_ms = (q_feed_start_lh / 1000) / 3600
p_verlust_druck_haupt = (r_druck_haupt * q_ms**2) / 100000
p_effektiv_start = p_system - p_verlust_druck_haupt

membran_daten = []
total_permeat = 0

# Membran-Schleife
for i in range(anzahl_membranen):
    f_in = q_feed_start_lh / anzahl_membranen
    p_in = p_effektiv_start 
    pi = (tds_feed / 100) * 0.07
    ndp = max(0, p_in - pi)
    q_p = m_flaeche * a_wert * ndp * tcf * 1000
    if q_p > f_in * 0.95: q_p = f_in * 0.95 
    q_c = f_in - q_p
    total_permeat += q_p
    membran_daten.append({"id": i, "q_c": q_c, "q_p": q_p})

# Hydraulik Sammelleitungen berechnen
total_konzentrat = q_feed_start_lh - total_permeat
p_vor_drossel = p_effektiv_start - 0.2 # Spacer Verlust initial

if anzahl_membranen == 1:
    r_out = berechne_hydraulischen_widerstand(cfg_sammel['d_out'], cfg_sammel['l_out'], [], cfg_sammel['b_out'])
    p_verlust_out = (r_out * ((total_konzentrat / 1000) / 3600)**2) / 100000
    p_vor_drossel -= p_verlust_out
else:
    # Widerstand der Einzelzweige (M1 vs Mn)
    r_m1 = berechne_hydraulischen_widerstand(cfg_sammel['d_m1'], cfg_sammel['l_m1'], [], cfg_sammel['b_m1'], zeta_extra=0)
    r_mn = berechne_hydraulischen_widerstand(cfg_sammel['d_mn'], cfg_sammel['l_mn'], [], cfg_sammel['b_mn'], zeta_extra=1.3)
    
    # Vereinfachte Annahme für Druckverlust vor dem Sammelpunkt:
    # Wir nehmen den Pfad der "ungünstigsten" Membrane (Mn mit Umlenkung)
    q_c_einzel = total_konzentrat / anzahl_membranen
    p_verlust_abzweig = (r_mn * ((q_c_einzel / 1000) / 3600)**2) / 100000
    
    # Gemeinsames Sammelrohr
    r_out = berechne_hydraulischen_widerstand(cfg_sammel['d_out'], cfg_sammel['l_out'], [], cfg_sammel['b_out'])
    p_verlust_out = (r_out * ((total_konzentrat / 1000) / 3600)**2) / 100000
    
    p_vor_drossel -= (p_verlust_abzweig + p_verlust_out)

abzubauender_druck = max(0.1, p_vor_drossel - 0.5) 
empfohlene_drossel_mm = empfehle_drossel_durchmesser(total_konzentrat, abzubauender_druck)

# --- UI OUTPUT ---
st.subheader("📊 Anlagen-Performance")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Gesamt Permeat", f"{total_permeat:.1f} l/h")
c2.metric("Gesamt Konzentrat", f"{total_konzentrat:.1f} l/h")
c3.metric("Feed Bedarf", f"{q_feed_start_lh:.1f} l/h")
c4.metric("Ist-Ausbeute", f"{(total_permeat / q_feed_start_lh * 100):.1f} %" if q_feed_start_lh > 0 else "0 %")

st.divider()
st.subheader("🛑 Konzentrat-Abgang & Drossel")
v1, v2, v3 = st.columns(3)
v1.metric("Druck vor Drossel", f"{p_vor_drossel:.2f} bar")
v2.metric("Druckabbau Wunsch", f"{abzubauender_druck:.2f} bar")
v3.metric("Empfohlene Drossel", f"Ø {empfohlene_drossel_mm:.2f} mm")
