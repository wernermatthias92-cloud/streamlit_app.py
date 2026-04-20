import streamlit as st
import math
import pandas as pd

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")
st.title("💧 RO-Anlagen Planer & Hydraulik-Netzwerk")

# --- Hydraulik-Kernfunktionen ---
def berechne_widerstand(d_inner_mm, laenge_mm, drosseln_liste, anzahl_90_grad):
    """Gibt einen geometrischen Widerstandswert zurück, um Flüsse aufzuteilen"""
    if d_inner_mm <= 0: return 1e9
    d_m = d_inner_mm / 1000
    area = math.pi * (d_m/2)**2
    # Lambda ca. 0.03
    r_rohr = 0.03 * (laenge_mm/1000 / d_m) / (area**2)
    r_drossel = sum([1.5 * (d_inner_mm/d)**2 / (area**2) for d in drosseln_liste if d > 0])
    r_bogen = anzahl_90_grad * 1.2 / (area**2)
    return r_rohr + r_drossel + r_bogen

def berechne_druckverlust_flow(flow_lh, d_inner_mm, laenge_mm, drosseln_liste, anzahl_90_grad):
    if flow_lh <= 0 or d_inner_mm <= 0: return 0
    q_ms = (flow_lh / 1000) / 3600  
    d_m = d_inner_mm / 1000
    v = q_ms / (math.pi * (d_m/2)**2)
    dyn_druck = 1000 * v**2 / 2
    
    p_pa = 0.03 * (laenge_mm/1000 / d_m) * dyn_druck
    for d_drossel in drosseln_liste:
        if d_drossel > 0: p_pa += 1.5 * dyn_druck * (d_inner_mm / d_drossel)**2
    p_pa += anzahl_90_grad * 1.2 * dyn_druck
    return p_pa / 100000 # in bar

def empfehle_drossel_durchmesser(flow_lh, delta_p_bar):
    """Berechnet den Blendendurchmesser für einen bestimmten Druckabfall"""
    if flow_lh <= 0 or delta_p_bar <= 0: return 0.0
    q_ms = (flow_lh / 1000) / 3600
    delta_p_pa = delta_p_bar * 100000
    # Angenommener Zeta-Wert für eine Standard-Blende/Drossel: 2.5
    # A = Q / sqrt( (2 * deltaP) / (zeta * rho) )
    v_spalt = math.sqrt((2 * delta_p_pa) / (2.5 * 1000))
    area_m2 = q_ms / v_spalt
    d_m = math.sqrt((4 * area_m2) / math.pi)
    return d_m * 1000 # in mm

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Verschaltung & Aufbau")
    schaltung = st.selectbox("Verschaltung", ["In Reihe (Konzentrat -> Feed)", "Parallel (Aufteilung)"])
    anzahl_membranen = st.number_input("Anzahl Membranen", 1, 5, 2)
    ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 90, 50)
    
    st.header("2. Membrane & System")
    m_flaeche = st.number_input("Filterfläche (m²)", value=7.5)
    m_test_flow = st.number_input("Nennleistung (l/h)", value=380.0)
    m_test_druck = st.number_input("Test-Druck (bar)", value=15.5)
    tds_feed = st.number_input("Feed TDS (ppm)", value=500)
    temp = st.slider("Temperatur (°C)", 10, 50, 15)
    p_system = st.number_input("Systemdruck nach Pumpe (bar)", value=15.0)

    st.header("3. Zuleitungen (Druckseite)")
    d_druck = st.number_input("Ø Hauptleitung (mm)", value=15.0)
    l_druck = st.number_input("Länge Hauptleitung (mm)", value=2000.0)
    
    hat_t_stueck = st.checkbox("Hauptleitung durch T-Stück aufteilen")
    if hat_t_stueck:
        st.caption("Strang A & B werden physikalisch balanciert!")
        colA, colB = st.columns(2)
        d_a = colA.number_input("Ø Strang A", value=15.0)
        l_a = colA.number_input("Länge A", value=1000.0)
        d_b = colB.number_input("Ø Strang B", value=10.0) # Standardmäßig dünner, um Balancing zu zeigen
        l_b = colB.number_input("Länge B", value=1000.0)
        
        # Sub-Aufteilung (Einfachheitshalber nur für Strang A demonstriert)
        sub_t = colA.checkbox("Strang A weiter aufteilen?")
        if sub_t:
            st.warning("Für eine noch tiefere Verschachtelung empfiehlt sich eine echte Rohrnetzberechnungs-Software. Wir rechnen hier mit dem schlechtesten Strang weiter.")

    st.header("4. Konzentrat- & Zwischenleitungen")
    leitungen_konz = []
    if schaltung == "In Reihe (Konzentrat -> Feed)":
        for i in range(anzahl_membranen - 1):
            with st.expander(f"Leitung: Membran {i+1} -> Membran {i+2}"):
                leitungen_konz.append({
                    "d": st.number_input(f"Ø Innen (mm)", value=15.0, key=f"d_k_{i}"),
                    "l": st.number_input(f"Länge (mm)", value=500.0, key=f"l_k_{i}"),
                    "b": st.number_input(f"Bögen", 0, 10, 2, key=f"b_k_{i}")
                })
    else:
        for i in range(anzahl_membranen - 1):
            with st.expander(f"Sammelleitung T-Stück {i+1} (Mischung)"):
                st.caption(f"Leitung nach der Einmündung von Membran {i+2}")
                leitungen_konz.append({
                    "d": st.number_input(f"Ø Innen (mm)", value=20.0, key=f"d_p_{i}"),
                    "l": st.number_input(f"Länge (mm)", value=300.0, key=f"l_p_{i}"),
                    "b": st.number_input(f"Bögen", 0, 10, 0, key=f"b_p_{i}")
                })

# --- BERECHNUNG ---
# Membran-Konstanten
tcf = math.exp(2640 * (1/298.15 - 1/(temp + 273.15)))
a_wert = (m_test_flow/1000) / (m_flaeche * (m_test_druck - (1500/100*0.07)))

# 1. Start-Bedarf schätzen
ndp_start = p_system - ((tds_feed / 100) * 0.07)
q_p_approx = (anzahl_membranen * m_flaeche) * a_wert * max(0, ndp_start) * tcf * 1000
q_feed_start_lh = q_p_approx / (ausbeute_pct / 100) if (ausbeute_pct > 0 and q_p_approx > 0) else 0

if ndp_start <= 0:
    st.error("Systemdruck zu gering!")
    st.stop()

# 2. Zuleitung Hauptstrang
p_verlust_haupt = berechne_druckverlust_flow(q_feed_start_lh, d_druck, l_druck, [], 0)
p_nach_haupt = p_system - p_verlust_haupt

# 3. Hydraulisches Balancing im T-Stück
verlust_zuleitung_gesamt = p_verlust_haupt
if hat_t_stueck:
    # Widerstand berechnen (vereinfachte Geometrie-Faktoren)
    res_a = berechne_widerstand(d_a, l_a, [], 0)
    res_b = berechne_widerstand(d_b, l_b, [], 0)
    
    # Fluss teilt sich umgekehrt proportional zur Wurzel der Widerstände auf
    anteil_a = math.sqrt(res_b) / (math.sqrt(res_a) + math.sqrt(res_b))
    anteil_b = 1.0 - anteil_a
    
    flow_a = q_feed_start_lh * anteil_a
    flow_b = q_feed_start_lh * anteil_b
    
    # Druckverlust ist nun in beiden Strängen (näherungsweise) gleich!
    p_verlust_zweig = berechne_druckverlust_flow(flow_a, d_a, l_a, [], 0)
    verlust_zuleitung_gesamt += p_verlust_zweig
    
    st.sidebar.success(f"Balancing: Strang A führt {anteil_a*100:.1f}%, Strang B {anteil_b*100:.1f}% des Wassers.")

# Startdruck für Membranen
p_effektiv_start = p_system - verlust_zuleitung_gesamt
current_feed_flow = q_feed_start_lh
current_tds = tds_feed
current_p = p_effektiv_start

membran_daten = []
total_permeat = 0
konzentrat_druck_verlauf = current_p

# 4. Membran-Schleife & Zwischenleitungen
for i in range(anzahl_membranen):
    # Hydraulik vor Modul
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
    tds_p = tds_in * (1 - 0.99)
    tds_c = ((f_in * tds_in) - (q_p * tds_p)) / q_c if q_c > 0 else tds_in
    total_permeat += q_p

    membran_daten.append({
        "Membran": f"Modul {i+1}",
        "Eingangsdruck (bar)": round(p_in, 2),
        "Permeat (l/h)": round(q_p, 1),
        "Konzentrat (l/h)": round(q_c, 1),
        "Feed TDS (ppm)": round(tds_in, 0)
    })

    # Hydraulik NACH Modul (Vorbereitung für nächstes Modul oder End-Ventil)
    if schaltung == "In Reihe (Konzentrat -> Feed)":
        if i < anzahl_membranen - 1:
            # Druckverlust der eingestellten Zwischenleitung
            l_cfg = leitungen_konz[i]
            p_verlust_zwischen = berechne_druckverlust_flow(q_c, l_cfg['d'], l_cfg['l'], [], l_cfg['b'])
            current_p = p_in - 0.2 - p_verlust_zwischen # 0.2 bar Spacer-Verlust + Leitungsverlust
        current_feed_flow = q_c
        current_tds = tds_c
        konzentrat_druck_verlauf = current_p

# 5. Konzentrat-Regelventil (Enddrossel)
end_konzentrat_flow = q_c if schaltung == "In Reihe (Konzentrat -> Feed)" else (q_feed_start_lh - total_permeat)

# Bei Parallelschaltung: Sammelleitung berechnen
if schaltung == "Parallel":
    current_sammel_flow = q_feed_start_lh / anzahl_membranen - membran_daten[0]["Permeat (l/h)"] # Start mit Membran 1
    p_sammel = p_effektiv_start - 0.2 # Druck nach Membran 1
    for i in range(anzahl_membranen - 1):
        l_cfg = leitungen_konz[i]
        # T-Stück Verlust (Einmündung) + Rohrreibung
        p_verlust = berechne_druckverlust_flow(current_sammel_flow, l_cfg['d'], l_cfg['l'], [], l_cfg['b'])
        p_sammel -= (p_verlust + 0.05) # 0.05 bar pauschal für T-Stück Turbulenz
        # Nächstes Konzentrat fließt hinzu
        current_sammel_flow += (q_feed_start_lh / anzahl_membranen - membran_daten[i+1]["Permeat (l/h)"])
    konzentrat_druck_verlauf = p_sammel

# Ventildurchmesser berechnen
# Der Restdruck muss vernichtet werden. Wir lassen 0.5 bar als "Abfluss-Staudruck" übrig.
abzubauender_druck = max(0.1, konzentrat_druck_verlauf - 0.5) 
empfohlene_drossel_mm = empfehle_drossel_durchmesser(end_konzentrat_flow, abzubauender_druck)

# --- UI OUTPUT ---
st.subheader("📊 Anlagen-Performance")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Gesamt Permeat", f"{total_permeat:.1f} l/h")
c2.metric("Gesamt Konzentrat", f"{end_konzentrat_flow:.1f} l/h")
c3.metric("Benötigter Speisestrom", f"{q_feed_start_lh:.1f} l/h")
c4.metric("Ist-Ausbeute", f"{(total_permeat / q_feed_start_lh * 100):.1f} %" if q_feed_start_lh > 0 else "0 %")

st.dataframe(pd.DataFrame(membran_daten), use_container_width=True)

st.divider()
st.subheader("🛑 Auslegung Konzentrat-Regelventil (End-Drossel)")
st.write(f"Um die Ziel-Ausbeute zu erreichen, muss das Ventil den verbleibenden Systemdruck abbauen, damit genau **{end_konzentrat_flow:.1f} l/h** Konzentrat fließen.")

v1, v2, v3 = st.columns(3)
v1.metric("Restdruck vor Ventil", f"{konzentrat_druck_verlauf:.2f} bar")
v2.metric("Abzubauender Druck ($\Delta$P)", f"{abzubauender_druck:.2f} bar")
v3.metric("Empfohlene Blenden-Bohrung", f"Ø {empfohlene_drossel_mm:.2f} mm", help="Basierend auf einer Blende mit Zeta = 2.5")

if empfohlene_drossel_mm < 1.0:
    st.warning("⚠️ Der berechnete Querschnitt ist extrem klein (< 1 mm). Es besteht hohe Verstopfungsgefahr durch Partikel. Ein Nadelventil ist zwingend erforderlich.")
elif empfohlene_drossel_mm > 8.0:
    st.info("💡 Der Querschnitt ist sehr groß. Möglicherweise ist der Systemdruck insgesamt zu niedrig angesetzt.")
