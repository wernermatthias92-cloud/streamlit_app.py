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
    
    # zeta_extra wird genutzt für T-Stücke (z.B. seitliche Einmündung)
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
    st.header("1. Verschaltung & Aufbau")
    schaltung = st.selectbox("Verschaltung", ["In Reihe (Konzentrat -> Feed)", "Parallel (Aufteilung)"])
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

    st.header("3. Rohrleitungen Zuleitung")
    
    with st.expander("Zuleitung ZUR Pumpe (Saugseite)", expanded=False):
        d_saug = st.number_input("Ø Innen Saugseite (mm)", value=20.0, key="ds")
        l_saug = st.number_input("Länge (mm)", value=1000.0, key="ls")
        b_saug = st.number_input("Anzahl 90° Bögen", 0, 10, 0, key="bs")
        n_drossel_saug = st.number_input("Anzahl Drosseln", 0, 5, 0, key="nds")
        drosseln_saug = [st.number_input(f"Ø Drossel {i+1} (mm)", value=10.0, key=f"drs_{i}") for i in range(n_drossel_saug)]
    
    r_saug = berechne_hydraulischen_widerstand(d_saug, l_saug, drosseln_saug, b_saug)

    with st.expander("Zuleitung NACH Pumpe (Druckseite)", expanded=False):
        d_druck = st.number_input("Ø Hauptleitung (mm)", value=15.0)
        l_druck = st.number_input("Länge Hauptleitung (mm)", value=2000.0)
        b_druck = st.number_input("Bögen Hauptleitung", 0, 10, 0)
        r_druck_haupt = berechne_hydraulischen_widerstand(d_druck, l_druck, [], b_druck)
        
        r_netzwerk = 0
        hat_t_stueck = st.checkbox("Hauptleitung durch T-Stück aufteilen")
        
        pct_a, pct_b, pct_a1, pct_b1 = 1.0, 0.0, 0.0, 0.0
        sub_a, sub_b = False, False

        if hat_t_stueck:
            st.markdown("#### Strang A")
            colA1, colA2 = st.columns(2)
            d_a = colA1.number_input("Ø Strang A", value=15.0)
            l_a = colA2.number_input("Länge A", value=1000.0)
            
            sub_a = st.checkbox("↳ Strang A in A1 & A2 aufteilen")
            if sub_a:
                cA1, cA2 = st.columns(2)
                d_a1 = cA1.number_input("Ø A1", value=10.0)
                l_a1 = cA1.number_input("Länge A1", value=500.0)
                d_a2 = cA2.number_input("Ø A2", value=10.0)
                l_a2 = cA2.number_input("Länge A2", value=500.0)
                r_a1 = berechne_hydraulischen_widerstand(d_a1, l_a1, [], 0)
                r_a2 = berechne_hydraulischen_widerstand(d_a2, l_a2, [], 0)
                r_a_sub = r_parallel(r_a1, r_a2)
            else:
                r_a_sub = 0
                
            r_a_main = berechne_hydraulischen_widerstand(d_a, l_a, [], 0)
            r_a_tot = r_a_main + r_a_sub

            st.markdown("#### Strang B")
            colB1, colB2 = st.columns(2)
            d_b = colB1.number_input("Ø Strang B", value=15.0)
            l_b = colB2.number_input("Länge B", value=1000.0)
            
            sub_b = st.checkbox("↳ Strang B in B1 & B2 aufteilen")
            if sub_b:
                cB1, cB2 = st.columns(2)
                d_b1 = cB1.number_input("Ø B1", value=10.0)
                l_b1 = cB1.number_input("Länge B1", value=500.0)
                d_b2 = cB2.number_input("Ø B2", value=10.0)
                l_b2 = cB2.number_input("Länge B2", value=500.0)
                r_b1 = berechne_hydraulischen_widerstand(d_b1, l_b1, [], 0)
                r_b2 = berechne_hydraulischen_widerstand(d_b2, l_b2, [], 0)
                r_b_sub = r_parallel(r_b1, r_b2)
            else:
                r_b_sub = 0
                
            r_b_main = berechne_hydraulischen_widerstand(d_b, l_b, [], 0)
            r_b_tot = r_b_main + r_b_sub

            r_netzwerk = r_parallel(r_a_tot, r_b_tot)

            pct_a = math.sqrt(r_b_tot) / (math.sqrt(r_a_tot) + math.sqrt(r_b_tot))
            pct_b = 1.0 - pct_a
            if sub_a: pct_a1 = math.sqrt(r_a2) / (math.sqrt(r_a1) + math.sqrt(r_a2))
            if sub_b: pct_b1 = math.sqrt(r_b2) / (math.sqrt(r_b1) + math.sqrt(r_b2))

        st.divider()
        if hat_t_stueck:
            st.success(f"**Live Balancing im Netzwerk:**\nStrang A führt {pct_a*100:.1f} % des Wassers.\nStrang B führt {pct_b*100:.1f} % des Wassers.")
            if sub_a: st.info(f"Aufteilung Strang A: A1 ({pct_a1*100:.1f}%) | A2 ({(1-pct_a1)*100:.1f}%)")
            if sub_b: st.info(f"Aufteilung Strang B: B1 ({pct_b1*100:.1f}%) | B2 ({(1-pct_b1)*100:.1f}%)")
        else:
            st.success("**Live Balancing:**\n100.0 % des Wassers fließen ungeteilt durch die Hauptleitung.")

    st.header("4. Konzentrat- & Zwischenleitungen")
    leitungen_konz = []
    leitung_out = None
    
    if schaltung == "In Reihe (Konzentrat -> Feed)":
        for i in range(anzahl_membranen - 1):
            with st.expander(f"Zwischenleitung: Membran {i+1} -> {i+2}"):
                leitungen_konz.append({
                    "d": st.number_input(f"Ø Innen (mm)", value=15.0, key=f"d_k_{i}"),
                    "l": st.number_input(f"Länge (mm)", value=500.0, key=f"l_k_{i}"),
                    "b": st.number_input(f"Bögen", 0, 10, 2, key=f"b_k_{i}")
                })
        
        with st.expander(f"Konzentrat-Auslassleitung (nach Membran {anzahl_membranen})", expanded=True):
            st.caption("Diese Leitung führt zur finalen Drossel/Regelventil.")
            leitung_out = {
                "d": st.number_input("Ø Innen Auslass (mm)", value=15.0, key="d_out_r"),
                "l": st.number_input("Länge Auslass (mm)", value=1000.0, key="l_out_r"),
                "b": st.number_input("Bögen Auslass", 0, 10, 2, key="b_out_r")
            }
            
    elif schaltung == "Parallel":
        for i in range(anzahl_membranen):
            with st.expander(f"Konzentratleitung: Membran {i+1} -> Mischleitung"):
                if i == 0:
                    st.caption("💡 Leitung 1 geht **gerade** in die Mischleitung (kein T-Stück Umlenkverlust).")
                else:
                    st.caption("💡 Leitung mündet **seitlich** in die Mischleitung (inkl. T-Stück Umlenkverlust).")
                leitungen_konz.append({
                    "d": st.number_input(f"Ø Innen (mm)", value=15.0, key=f"d_p_{i}"),
                    "l": st.number_input(f"Länge (mm)", value=500.0, key=f"l_p_{i}"),
                    "b": st.number_input(f"Bögen", 0, 10, 0, key=f"b_p_{i}")
                })
                
        with st.expander("Mischleitung nach letztem Zusammenfluss bis Drossel", expanded=True):
            st.caption("Sammelt das gesamte Konzentrat und führt zum End-Regelventil.")
            leitung_out = {
                "d": st.number_input("Ø Innen Mischleitung (mm)", value=20.0, key="d_out_p"),
                "l": st.number_input("Länge Mischleitung (mm)", value=1500.0, key="l_out_p"),
                "b": st.number_input("Bögen Mischleitung", 0, 10, 2, key="b_out_p")
            }

# --- BERECHNUNG DER ANLAGE ---
tcf = math.exp(2640 * (1/298.15 - 1/(temp + 273.15)))
a_wert = (m_test_flow/1000) / (m_flaeche * (m_test_druck - (1500/100*0.07)))

# Feed-Bedarf schätzen
ndp_start = p_system - ((tds_feed / 100) * 0.07)
q_p_approx = (anzahl_membranen * m_flaeche) * a_wert * max(0, ndp_start) * tcf * 1000
q_feed_start_lh = q_p_approx / (ausbeute_pct / 100) if (ausbeute_pct > 0 and q_p_approx > 0) else 0

if ndp_start <= 0:
    st.error("Systemdruck zu gering, um den osmotischen Druck zu überwinden!")
    st.stop()

# Druckverluste Zuleitung in bar
q_ms = (q_feed_start_lh / 1000) / 3600
p_verlust_saug = (r_saug * q_ms**2) / 100000 
p_verlust_druck_haupt = (r_druck_haupt * q_ms**2) / 100000
p_verlust_netzwerk = (r_netzwerk * q_ms**2) / 100000 if hat_t_stueck else 0

p_effektiv_start = p_system - p_verlust_druck_haupt - p_verlust_netzwerk

current_feed_flow = q_feed_start_lh
current_tds = tds_feed
current_p = p_effektiv_start

membran_daten = []
total_permeat = 0

# Membran-Schleife
for i in range(anzahl_membranen):
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
    tds_p = tds_in * (1 - m_rueckhalt)
    tds_c = ((f_in * tds_in) - (q_p * tds_p)) / q_c if q_c > 0 else tds_in
    total_permeat += q_p

    membran_daten.append({
        "Membran": f"Modul {i+1}",
        "Eingangsdruck (bar)": round(p_in, 2),
        "Permeat (l/h)": round(q_p, 1),
        "Konzentrat (l/h)": round(q_c, 1),
        "Feed TDS (ppm)": round(tds_in, 0)
    })

    if schaltung == "In Reihe (Konzentrat -> Feed)":
        druck_nach_spacer = p_in - 0.2
        if i < anzahl_membranen - 1:
            l_cfg = leitungen_konz[i]
            r_zwischen = berechne_hydraulischen_widerstand(l_cfg['d'], l_cfg['l'], [], l_cfg['b'])
            p_verlust_zwischen = (r_zwischen * ((q_c / 1000) / 3600)**2) / 100000
            current_p = druck_nach_spacer - p_verlust_zwischen 
        else:
            current_p = druck_nach_spacer 
            
        current_feed_flow = q_c
        current_tds = tds_c

# Enddrossel & Auslassleitung Berechnungen
end_konzentrat_flow = q_feed_start_lh - total_permeat
konzentrat_druck_verlauf = 0

if schaltung == "In Reihe (Konzentrat -> Feed)":
    r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
    p_verlust_out = (r_out * ((end_konzentrat_flow / 1000) / 3600)**2) / 100000
    konzentrat_druck_verlauf = current_p - p_verlust_out
    
elif schaltung == "Parallel":
    p_sammel_kandidaten = []
    # Druckabfall für jede Zuleitung vom Modul in die Mischleitung berechnen
    for i in range(anzahl_membranen):
        l_cfg = leitungen_konz[i]
        q_c_branch = membran_daten[i]["Konzentrat (l/h)"]
        
        # Modul 1 = gerade (zeta 0), alle anderen = seitlich ins T-Stück (zeta 1.3)
        zeta_einmuendung = 0.0 if i == 0 else 1.3 
        
        r_branch = berechne_hydraulischen_widerstand(l_cfg['d'], l_cfg['l'], [], l_cfg['b'], zeta_extra=zeta_einmuendung)
        p_verlust_branch = (r_branch * ((q_c_branch / 1000) / 3600)**2) / 100000
        
        # Druck nach Membran ist Eingangsdruck - 0.2 bar Spacerverlust
        p_branch_out = (membran_daten[i]["Eingangsdruck (bar)"] - 0.2) - p_verlust_branch
        p_sammel_kandidaten.append(p_branch_out)
        
    # Wir nehmen den hydraulisch ungünstigsten Zweig (niedrigster Druck), 
    # um sicherzustellen, dass das Endventil funktioniert.
    p_manifold = min(p_sammel_kandidaten)
    
    # Druckverlust der finalen Mischleitung
    r_out = berechne_hydraulischen_widerstand(leitung_out['d'], leitung_out['l'], [], leitung_out['b'])
    p_verlust_out = (r_out * ((end_konzentrat_flow / 1000) / 3600)**2) / 100000
    konzentrat_druck_verlauf = p_manifold - p_verlust_out

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

st.subheader("🔧 Hydraulik-Analyse Zuleitungen")
h1, h2 = st.columns(2)
with h1:
    st.markdown("**Saugseite (Vor Pumpe)**")
    st.info(f"Druckverlust Saugseite: **{p_verlust_saug:.3f} bar**")
    if p_verlust_saug > 0.3: st.warning("⚠️ Kavitationsgefahr! Saugwiderstand zu hoch.")
with h2:
    st.markdown("**Druckseite (Pumpe -> Membran)**")
    st.write(f"- Verlust Hauptleitung: {p_verlust_druck_haupt:.3f} bar")
    if hat_t_stueck:
        st.write(f"- Verlust im Split-Netzwerk: {p_verlust_netzwerk:.3f} bar")
    st.success(f"Effektiver Druck an Anlage: **{p_effektiv_start:.2f} bar**")

st.divider()
st.subheader("🛑 Auslegung Konzentrat-Regelventil (End-Drossel)")
v1, v2, v3 = st.columns(3)
v1.metric("Restdruck vor Ventil", f"{konzentrat_druck_verlauf:.2f} bar")
v2.metric("Abzubauender Druck ($\Delta$P)", f"{abzubauender_druck:.2f} bar")
v3.metric("Empfohlener Drosseldurchmesser", f"Ø {empfohlene_drossel_mm:.2f} mm")
