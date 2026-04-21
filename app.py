import streamlit as st
import pandas as pd
import math

from hydraulik.widerstand import berechne_hydraulischen_widerstand, r_parallel
from system.reihe import simuliere_reihe
from system.parallel import simuliere_parallel
from system.parallel_drossel import simuliere_parallel_drossel
from utils.pdf_export import generiere_pdf

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")

with st.sidebar:
    with st.expander("1. Verschaltung & Aufbau", expanded=True):
        schaltung = st.selectbox("Verschaltung", ["Parallel (Aufteilung)", "In Reihe (Konzentrat -> Feed)"])
        
        if schaltung == "In Reihe (Konzentrat -> Feed)":
            anzahl_membranen = st.number_input("Anzahl Membranen", 1, 10, 2)
            ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 90, 50)
            auslegungs_modus = "Ziel-Ausbeute" 
            drossel_vorgabe_mm = 0
            
        else:
            st.info("💡 Membran-Anzahl wird dynamisch aus Sektion 3 berechnet.")
            anzahl_membranen = 1 
            auslegungs_modus = st.radio("Auslegungs-Modus", ["Ziel-Ausbeute vorgeben", "Drossel-Ø vorgeben (Digital Twin)"])
            
            if auslegungs_modus == "Ziel-Ausbeute vorgeben":
                ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 90, 50)
                drossel_vorgabe_mm = 0
            else:
                drossel_vorgabe_mm = st.number_input("Fester Drossel-Ø (mm)", min_value=0.1, value=1.2, step=0.1)
                ausbeute_pct = 0
    
    with st.expander("2. Membrane & System", expanded=False):
        m_flaeche = st.number_input("Filterfläche (m²)", value=7.5)
        m_test_flow = st.number_input("Nennleistung (l/h)", value=568.0)
        m_test_druck = st.number_input("Test-Druck (bar)", value=9.3)
        m_rueckhalt = st.slider("Rückhalt (%)", 90.0, 99.9, 98.0) / 100
        st.divider()
        tds_feed = st.number_input("Feed TDS (ppm)", value=96)
        temp = st.slider("Temperatur (°C)", 10, 50, 13)
        
        st.divider()
        st.markdown("**Pumpen-Parameter**")
        if auslegungs_modus == "Ziel-Ausbeute vorgeben" or schaltung == "In Reihe (Konzentrat -> Feed)":
            p_system = st.number_input("Statischer Systemdruck nach Pumpe (bar)", value=9.4)
            pumpe_p_max = p_system 
            pumpe_q_max = 0 
        else:
            st.caption("Trage die Maximalwerte der Pumpenkennlinie ein.")
            pumpe_p_max = st.number_input("Max. Druck bei 0 Durchfluss (bar)", value=11.5, step=0.5)
            pumpe_q_max = st.number_input("Max. Durchfluss bei 0 bar (l/h)", value=2500.0, step=100.0)
            p_system = pumpe_p_max 

    with st.expander("3. Rohrleitungen Zuleitung", expanded=False):
        st.markdown("**Saugseite (Vor Pumpe)**")
        p_zulauf = st.number_input("Zulaufdruck (z.B. Hausanschluss in bar)", value=3.0, step=0.5, key="pz")
        d_saug = st.number_input("Ø Innen Saugseite (mm)", value=13.2, key="ds")
        l_saug = st.number_input("Länge (mm)", min_value=1.0, value=1000.0, step=10.0, key="ls")
        b_saug = st.number_input("Anzahl 90° Bögen", 0, 10, 0, key="bs")
        n_drossel_saug = st.number_input("Anzahl Drosseln", 0, 5, 0, key="nds")
        drosseln_saug = [st.number_input(f"Ø Drossel {i+1} (mm)", value=10.0, key=f"drs_{i}") for i in range(n_drossel_saug)]
        r_saug = berechne_hydraulischen_widerstand(d_saug, l_saug, drosseln_saug, b_saug)
        
        st.divider()
        st.markdown("**Druckseite (Hauptleitung)**")
        d_druck = st.number_input("Ø Hauptleitung (mm)", value=13.2)
        l_druck = st.number_input("Länge Hauptleitung (mm)", min_value=1.0, value=400.0, step=10.0)
        b_druck = st.number_input("Bögen Hauptleitung", 0, 10, 0)
        r_druck_haupt = berechne_hydraulischen_widerstand(d_druck, l_druck, [], b_druck)
        
        r_netzwerk = 0
        hat_t_stueck, sub_a, sub_b = False, False, False
        flow_fractions, membran_namen = [1.0], ["Modul 1 (Haupt)"]
        
        if schaltung == "Parallel (Aufteilung)":
            hat_t_stueck = st.checkbox("Hauptleitung durch T-Stück aufteilen", value=True)
            if hat_t_stueck:
                st.markdown("#### Strang A")
                ca1, ca2, ca3 = st.columns(3)
                d_a = ca1.number_input("Ø A", value=13.2)
                l_a = ca2.number_input("Länge A", value=150.0, min_value=1.0)
                b_a = ca3.number_input("Bögen A", value=1)
                
                sub_a = st.checkbox("↳ A aufteilen")
                r_a_sub = 0
                if sub_a:
                    cA1_1, cA1_2, cA1_3 = st.columns(3)
                    d_a1 = cA1_1.number_input("Ø A1", value=10.0)
                    l_a1 = cA1_2.number_input("Länge A1", value=500.0, min_value=1.0)
                    b_a1 = cA1_3.number_input("Bögen A1", value=0)
                    
                    cA2_1, cA2_2, cA2_3 = st.columns(3)
                    d_a2 = cA2_1.number_input("Ø A2", value=10.0)
                    l_a2 = cA2_2.number_input("Länge A2", value=500.0, min_value=1.0)
                    b_a2 = cA2_3.number_input("Bögen A2", value=0)
                    
                    r_a1 = berechne_hydraulischen_widerstand(d_a1, l_a1, [], b_a1)
                    r_a2 = berechne_hydraulischen_widerstand(d_a2, l_a2, [], b_a2)
                    r_a_sub = r_parallel(r_a1, r_a2)
                r_a_tot = berechne_hydraulischen_widerstand(d_a, l_a, [], b_a) + r_a_sub
                
                st.markdown("#### Strang B")
                cb1, cb2, cb3 = st.columns(3)
                d_b = cb1.number_input("Ø B", value=13.2)
                l_b = cb2.number_input("Länge B", value=150.0, min_value=1.0)
                b_b = cb3.number_input("Bögen B", value=1)
                
                sub_b = st.checkbox("↳ B aufteilen", value=True)
                r_b_sub = 0
                if sub_b:
                    cB1_1, cB1_2, cB1_3 = st.columns(3)
                    d_b1 = cB1_1.number_input("Ø B1", value=13.2)
                    l_b1 = cB1_2.number_input("Länge B1", value=200.0, min_value=1.0)
                    b_b1 = cB1_3.number_input("Bögen B1", value=0)
                    
                    cB2_1, cB2_2, cB2_3 = st.columns(3)
                    d_b2 = cB2_1.number_input("Ø B2", value=13.2)
                    l_b2 = cB2_2.number_input("Länge B2", value=200.0, min_value=1.0)
                    b_b2 = cB2_3.number_input("Bögen B2", value=0)
                    
                    r_b1 = berechne_hydraulischen_widerstand(d_b1, l_b1, [], b_b1)
                    r_b2 = berechne_hydraulischen_widerstand(d_b2, l_b2, [], b_b2)
                    r_b_sub = r_parallel(r_b1, r_b2)
                r_b_tot = berechne_hydraulischen_widerstand(d_b, l_b, [], b_b) + r_b_sub
                
                r_netzwerk = r_parallel(r_a_tot, r_b_tot)
                
                # --- PHYSIKALISCH KORREKTE FLUSS-AUFTEILUNG (CONDUCTANCE) ---
                R_MEM_BASE = 50000.0 
                r_path_a1 = (r_a_tot - r_a_sub + r_a1) if sub_a else r_a_tot
                r_path_a2 = (r_a_tot - r_a_sub + r_a2) if sub_a else r_a_tot
                r_path_b1 = (r_b_tot - r_b_sub + r_b1) if sub_b else r_b_tot
                r_path_b2 = (r_b_tot - r_b_sub + r_b2) if sub_b else r_b_tot
                
                c_a = 0 if sub_a else 1.0 / math.sqrt(r_path_a1 + R_MEM_BASE)
                c_a1 = 1.0 / math.sqrt(r_path_a1 + R_MEM_BASE) if sub_a else 0
                c_a2 = 1.0 / math.sqrt(r_path_a2 + R_MEM_BASE) if sub_a else 0
                
                c_b = 0 if sub_b else 1.0 / math.sqrt(r_path_b1 + R_MEM_BASE)
                c_b1 = 1.0 / math.sqrt(r_path_b1 + R_MEM_BASE) if sub_b else 0
                c_b2 = 1.0 / math.sqrt(r_path_b2 + R_MEM_BASE) if sub_b else 0
                
                c_total = c_a + c_a1 + c_a2 + c_b + c_b1 + c_b2
                
                if sub_a and sub_b:
                    flow_fractions, membran_namen = [c_a1/c_total, c_a2/c_total, c_b1/c_total, c_b2/c_total], ["A1","A2","B1","B2"]
                elif sub_a:
                    flow_fractions, membran_namen = [c_a1/c_total, c_a2/c_total, c_b/c_total], ["A1","A2","B"]
                elif sub_b:
                    flow_fractions, membran_namen = [c_a/c_total, c_b1/c_total, c_b2/c_total], ["A","B1","B2"]
                else:
                    flow_fractions, membran_namen = [c_a/c_total, c_b/c_total], ["A","B"]
                
                anzahl_membranen = len(flow_fractions)

    with st.expander("4. Konzentratleitungen", expanded=False):
        leitungen_konz, leitung_out = [], None
        if schaltung == "Parallel (Aufteilung)":
            if anzahl_membranen == 1:
                leitung_out = {"d": st.number_input("Ø Auslass (mm)", value=6.0, key="ko_d"), "l": st.number_input("Länge Auslass", value=300.0, min_value=1.0, key="ko_l"), "b": st.number_input("Bögen Auslass", value=2, key="ko_b")}
            else:
                for i in range(anzahl_membranen):
                    leitungen_konz.append({"d": st.number_input(f"Ø {membran_namen[i]}->T", value=8.4, key=f"ki_d_{i}"), "l": st.number_input(f"Länge {membran_namen[i]}", value=100.0, min_value=1.0, key=f"ki_l_{i}"), "b": st.number_input(f"Bögen {membran_namen[i]}", value=0, key=f"ki_b_{i}")})
                st.divider()
                leitung_out = {"d": st.number_input("Ø T->Drossel", value=6.0, key="kt_d"), "l": st.number_input("Länge T->Drossel", value=300.0, min_value=1.0, key="kt_l"), "b": st.number_input("Bögen T->Drossel", value=2, key="kt_b")}
        else:
            for i in range(anzahl_membranen - 1):
                leitungen_konz.append({
                    "d": st.number_input(f"Ø Innen {i+1}->{i+2}", value=15.0, key=f"d_k_{i}"),
                    "l": st.number_input(f"Länge {i+1}->{i+2} (mm)", min_value=1.0, value=500.0, step=10.0, key=f"l_k_{i}"),
                    "b": st.number_input(f"Bögen {i+1}->{i+2}", 0, 10, 2, key=f"b_k_{i}")
                })
            leitung_out = {
                "d": st.number_input("Ø Innen Auslass (mm)", value=15.0, key="d_out"),
                "l": st.number_input("Länge Auslass (mm)", min_value=1.0, value=1000.0, step=10.0, key="l_out"),
                "b": st.number_input("Bögen Auslass", 0, 10, 2, key="b_out")
            }

    with st.expander("5. Permeatleitungen", expanded=False):
        p_leitungen_konz, p_leitung_out, p_schlauch_out = [], None, None
        if schaltung == "Parallel (Aufteilung)":
            if anzahl_membranen == 1:
                st.markdown("**Permeatleitung bis Anlagenausgang**")
                p_leitung_out = {"d": st.number_input("Ø Permeat (mm)", value=13.2, key="po_d"), "l": st.number_input("Länge (mm)", value=1000.0, min_value=1.0, key="po_l"), "b": st.number_input("Bögen", value=0, key="po_b")}
            else:
                for i in range(anzahl_membranen):
                    p_leitungen_konz.append({"d": st.number_input(f"Ø {membran_namen[i]}->T (P)", value=13.2, key=f"pd_{i}"), "l": st.number_input(f"Länge {membran_namen[i]} (P)", value=300.0, min_value=1.0, key=f"pl_{i}"), "b": st.number_input(f"Bögen {membran_namen[i]} (P)", value=0, key=f"pb_{i}")})
                st.divider()
                st.markdown("**Sammelrohr Permeat**")
                p_leitung_out = {"d": st.number_input("Ø Sammelrohr (P)", value=13.2, key="pt_d"), "l": st.number_input("Länge Sammel (P)", value=1000.0, min_value=1.0, key="pt_l"), "b": st.number_input("Bögen Sammel (P)", value=0, key="pt_b")}
            
            st.divider()
            st.markdown("**Auslassschlauch (inkl. Höhenunterschied)**")
            p_schlauch_out = {
                "d": st.number_input("Ø Schlauch (mm)", value=13.2, key="ps_d"),
                "l": st.number_input("Länge Schlauch (mm)", value=1.0, min_value=1.0, step=10.0, key="ps_l"),
                "h": st.number_input("Höhendifferenz (m)", value=0.0, step=0.5, key="ps_h")
            }

# --- PDF WÖRTERBUCH (Lückenlos!) ---
inputs_fuer_pdf = {
    "schaltung": schaltung,
    "anzahl_membranen": anzahl_membranen,
    "ausbeute_pct": ausbeute_pct,
    "m_flaeche": m_flaeche,
    "m_test_flow": m_test_flow,
    "m_test_druck": m_test_druck,
    "m_rueckhalt": m_rueckhalt,
    "tds_feed": tds_feed,
    "temp": temp,
    "p_system": p_system,
    "p_zulauf": p_zulauf,
    "zuleitung_saug": {"d": d_saug, "l": l_saug, "b": b_saug},
    "zuleitung_druck": {"d": d_druck, "l": l_druck, "b": b_druck},
    "konz_leitungen": leitungen_konz,
    "konz_out": leitung_out,
    "perm_leitungen": p_leitungen_konz,
    "perm_out": p_leitung_out,
    "perm_schlauch": p_schlauch_out
}

# --- 3. BERECHNUNG ---
if schaltung == "In Reihe (Konzentrat -> Feed)":
    ergebnisse = simuliere_reihe(anzahl_membranen, ausbeute_pct, m_flaeche, m_test_flow, m_test_druck, m_rueckhalt, tds_feed, temp, p_system, r_saug, r_druck_haupt, leitungen_konz, leitung_out)
else:
    if auslegungs_modus == "Ziel-Ausbeute vorgeben":
        ergebnisse = simuliere_parallel(flow_fractions, membran_namen, ausbeute_pct, m_flaeche, m_test_flow, m_test_druck, m_rueckhalt, tds_feed, temp, p_system, r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, leitungen_konz, leitung_out, p_leitungen_konz, p_leitung_out, p_schlauch_out)
    else:
        ergebnisse = simuliere_parallel_drossel(flow_fractions, membran_namen, drossel_vorgabe_mm, m_flaeche, m_test_flow, m_test_druck, m_rueckhalt, tds_feed, temp, pumpe_p_max, pumpe_q_max, p_zulauf, r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, leitungen_konz, leitung_out, p_leitungen_konz, p_leitung_out, p_schlauch_out)

if ergebnisse.get("error"):
    st.error(ergebnisse["error"])
    st.stop()

# --- 4. UI MAIN WINDOW ---
col_title, col_btn = st.columns([4, 1])

with col_title:
    st.title("💧 RO-Anlagen Planer")

with col_btn:
    pdf_bytes = generiere_pdf(inputs_fuer_pdf, ergebnisse)
    st.write("") 
    st.write("")
    st.download_button(
        label="📄 PDF Protokoll Export",
        data=pdf_bytes,
        file_name="ro_anlagen_protokoll.pdf",
        mime="application/pdf"
    )

st.divider()

st.subheader("📊 Performance")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Gesamt Permeat", f"{ergebnisse['total_permeat']:.1f} l/h")
c2.metric("Gesamt Konzentrat", f"{ergebnisse['end_konzentrat_flow']:.1f} l/h")
c3.metric("Permeat TDS", f"{ergebnisse['total_permeat_tds']:.1f} ppm")
c4.metric("Konz. TDS", f"{ergebnisse['final_konzentrat_tds']:.0f} ppm")

st.dataframe(pd.DataFrame(ergebnisse['membran_daten']), use_container_width=True)
st.divider()

st.subheader("🛑 Hydraulik & Drossel")
v1, v2, v3 = st.columns(3)

if auslegungs_modus == "Drossel-Ø vorgeben (Digital Twin)":
    v1.metric("Pumpendruck (Real)", f"{ergebnisse.get('realer_pumpendruck', 0):.2f} bar")
else:
    v1.metric("Systemdruck (Statisch)", f"{p_system:.2f} bar")
    
v2.metric("P vor Ventil", f"{ergebnisse['konzentrat_druck_verlauf']:.2f} bar")

if auslegungs_modus == "Drossel-Ø vorgeben (Digital Twin)":
    v3.metric("Drossel Ø", f"Ø {drossel_vorgabe_mm:.2f} mm")
else:
    v3.metric("Empfohlener Drossel Ø", f"Ø {ergebnisse['empfohlene_drossel_mm']:.2f} mm")
