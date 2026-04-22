import streamlit as st
import pandas as pd
import math

# Eigene Module laden
from hydraulik.widerstand import berechne_hydraulischen_widerstand
from system.parallel import simuliere_parallel
from system.parallel_drossel import simuliere_parallel_drossel
from hydraulik.netzwerk import analysiere_gesamte_topologie
from utils.pdf_export import generiere_pdf

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")

# --- 1. UI SYNC LOGIK (l/h <-> m³/d) ---
if 'p_flow_lh' not in st.session_state:
    st.session_state.p_flow_lh = 568.0
if 'p_flow_m3' not in st.session_state:
    st.session_state.p_flow_m3 = 13.63

def sync_m3():
    st.session_state.p_flow_lh = st.session_state.p_flow_m3 * (1000 / 24)
def sync_lh():
    st.session_state.p_flow_m3 = st.session_state.p_flow_lh * (24 / 1000)

# --- 2. SIDEBAR EINGABEN ---
with st.sidebar:
    st.title("⚙️ Parameter")
    
    with st.expander("1. Verschaltung & Modus", expanded=True):
        st.info("🔧 Modus: Parallele Verschaltung")
        schaltung = "Parallel (Aufteilung)"
        
        auslegungs_modus = st.radio("Auslegungs-Modus", ["Ziel-Ausbeute vorgeben", "Drossel-Ø vorgeben (Digital Twin)"])
        
        if auslegungs_modus == "Ziel-Ausbeute vorgeben":
            ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 90, 50)
            drossel_vorgabe_mm = 0
        else:
            drossel_vorgabe_mm = st.number_input("Fester Drossel-Ø (mm)", min_value=0.1, value=1.2, step=0.1)
            ausbeute_pct = 0
    
    with st.expander("2. Membrane & System", expanded=True):
        st.markdown("**Datenblatt-Werte**")
        m_flaeche = st.number_input("Aktive Filterfläche (m²)", min_value=0.1, value=7.6, step=0.1)
        
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Permeat Flow (l/h)", key='p_flow_lh', on_change=sync_lh)
        with c2:
            st.number_input("Permeat Flow (m³/d)", key='p_flow_m3', on_change=sync_m3)
            
        m_test_flow_datasheet = st.session_state.p_flow_lh
        m_toleranz_pct = st.number_input("Toleranz / Alterung (%)", min_value=-50.0, max_value=20.0, value=-5.0, step=1.0)
        m_test_flow_effektiv = m_test_flow_datasheet * (1.0 + (m_toleranz_pct / 100.0))
        
        cp, cr = st.columns(2)
        with cp:
            m_test_druck = st.number_input("Test-Druck (bar)", value=9.3, format="%.1f", step=0.1)
        with cr:
            m_rueckhalt_int = st.number_input("Nominal Rejection (%)", min_value=0, max_value=100, value=98, step=1)
            m_rueckhalt = m_rueckhalt_int / 100.0
            
        m_test_tds = st.number_input("Test-Lösung (ppm NaCl)", value=500, step=50)

        st.divider()
        st.markdown("**Reale Bedingungen**")
        tds_feed = st.number_input("Feed TDS real (ppm)", value=96)
        temp = st.slider("Wassertemperatur real (°C)", 1, 50, 13)
        
        st.divider()
        if auslegungs_modus == "Ziel-Ausbeute vorgeben":
            p_system = st.number_input("Systemdruck nach Pumpe (bar)", value=9.4, step=0.1, format="%.1f")
            pumpe_p_max, pumpe_q_max = p_system, 0 
        else:
            pumpe_p_max = st.number_input("Max. Druck bei 0 l/h (bar)", value=11.5, step=0.5, format="%.1f")
            pumpe_q_max = st.number_input("Max. Durchfluss bei 0 bar (l/h)", value=2500.0, step=100.0)
            p_system = pumpe_p_max 

    with st.expander("3. Zuleitung & T-Stücke", expanded=False):
        p_zulauf = st.number_input("Zulaufdruck (bar)", value=3.0, step=0.1, key="pz")
        
        st.markdown("**Saugseite**")
        saug_cfg = {
            "d": st.number_input("Ø Innen Saug (mm)", value=13.2, key="ds"),
            "l": st.number_input("Länge Saug (mm)", value=1000.0, key="ls"),
            "b": st.number_input("Bögen Saug", 0, 10, 0, key="bs")
        }
        
        st.markdown("**Druckseite (Hauptleitung)**")
        druck_cfg = {
            "d": st.number_input("Ø Hauptleitung (mm)", value=13.2, key="dh"),
            "l": st.number_input("Länge Haupt (mm)", value=400.0, key="lh"),
            "b": st.number_input("Bögen Haupt", 0, 10, 0, key="bh")
        }
        
        st.divider()
        hat_t_stueck = st.checkbox("Hauptleitung durch T-Stück aufteilen", value=True)
        
        netzwerk_cfg = {"hat_t_stueck": hat_t_stueck}
        if hat_t_stueck:
            colA, colB = st.columns(2)
            with colA:
                st.markdown("Strang A")
                netzwerk_cfg.update({"d_a": st.number_input("Ø A", 13.2), "l_a": st.number_input("L A", 150.0), "b_a": st.number_input("B A", 1)})
                sub_a = st.checkbox("A aufteilen")
                netzwerk_cfg.update({"sub_a": sub_a, "d_a1": 0, "l_a1": 0, "b_a1": 0, "d_a2": 0, "l_a2": 0, "b_a2": 0})
                if sub_a:
                    netzwerk_cfg.update({"d_a1": st.number_input("Ø A1", 10.0), "l_a1": st.number_input("L A1", 500.0), "b_a1": 0,
                                        "d_a2": st.number_input("Ø A2", 10.0), "l_a2": st.number_input("L A2", 500.0), "b_a2": 0})
            with colB:
                st.markdown("Strang B")
                netzwerk_cfg.update({"d_b": st.number_input("Ø B", 13.2), "l_b": st.number_input("L B", 150.0), "b_b": st.number_input("B B", 1)})
                sub_b = st.checkbox("B aufteilen", True)
                netzwerk_cfg.update({"sub_b": sub_b, "d_b1": 0, "l_b1": 0, "b_b1": 0, "d_b2": 0, "l_b2": 0, "b_b2": 0})
                if sub_b:
                    netzwerk_cfg.update({"d_b1": st.number_input("Ø B1", 13.2), "l_b1": st.number_input("L B1", 200.0), "b_b1": 0,
                                        "d_b2": st.number_input("Ø B2", 13.2), "l_b2": st.number_input("L B2", 200.0), "b_b2": 0})
        else:
            # Defaults für Single-Modul
            netzwerk_cfg.update({"d_a": 0, "l_a": 0, "b_a": 0, "sub_a": False, "d_a1": 0, "l_a1": 0, "b_a1": 0, "d_a2": 0, "l_a2": 0, "b_a2": 0,
                                 "d_b": 0, "l_b": 0, "b_b": 0, "sub_b": False, "d_b1": 0, "l_b1": 0, "b_b1": 0, "d_b2": 0, "l_b2": 0, "b_b2": 0})

    # Hier bestimmen wir die Anzahl der Membranen basierend auf dem Netzwerk
    from hydraulik.netzwerk import berechne_feed_widerstaende
    _, m_namen, _ = berechne_feed_widerstaende(**netzwerk_cfg)
    anzahl_membranen = len(m_namen)

    with st.expander("4. Konzentratleitungen", expanded=False):
        konz_zweige = []
        for i in range(anzahl_membranen):
            konz_zweige.append({
                "d": st.number_input(f"Ø Konz {m_namen[i]} (mm)", 8.4, key=f"kd_{i}"), 
                "l": st.number_input(f"Länge Konz {i} (mm)", 100.0, key=f"kl_{i}"), 
                "b": 0
            })
        st.divider()
        konz_out = {
            "d": st.number_input("Ø Sammelrohr Konz (mm)", 6.0, key="kod"), 
            "l": st.number_input("Länge Sammel Konz (mm)", 300.0, key="kol"), 
            "b": 2
        }

    with st.expander("5. Permeatleitungen", expanded=False):
        perm_zweige = []
        for i in range(anzahl_membranen):
            perm_zweige.append({"d": 13.2, "l": 300.0, "b": 0})
        
        perm_out = {
            "d": st.number_input("Ø Sammelrohr Perm (mm)", 13.2, key="pod"), 
            "l": st.number_input("Länge Sammel Perm (mm)", 1000.0, key="pol"), 
            "b": 0
        }
        
        st.divider()
        st.markdown("**Auslassschlauch**")
        perm_schlauch = {
            "d": st.number_input("Ø Schlauch (mm)", 13.2, key="psd"),
            "l": st.number_input("Länge Schlauch (mm)", 1.0, key="psl"),
            "h": st.number_input("Höhendifferenz Austritt (m)", 0.0, step=0.5, key="psh")
        }

# --- 3. BERECHNUNGSLOGIK ---

# Hydraulik-Paket schnüren
hydraulik = analysiere_gesamte_topologie(
    saug_cfg, druck_cfg, netzwerk_cfg, 
    konz_zweige, konz_out, 
    perm_zweige, perm_out, perm_schlauch
)

if auslegungs_modus == "Ziel-Ausbeute vorgeben":
    ergebnisse = simuliere_parallel(
        hydraulik, ausbeute_pct, m_flaeche, m_test_flow_effektiv, 
        m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, p_system
    )
else:
    ergebnisse = simuliere_parallel_drossel(
        hydraulik, drossel_vorgabe_mm, m_flaeche, m_test_flow_effektiv, 
        m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, pumpe_p_max, pumpe_q_max, p_zulauf
    )

# --- 4. MAIN WINDOW ---
st.title("💧 RO-Anlagen Planer")

if ergebnisse.get("error"):
    st.error(ergebnisse["error"])
else:
    # PDF Export Vorbereitung
    inputs_fuer_pdf = {
        "schaltung": schaltung, "anzahl_membranen": anzahl_membranen, "ausbeute_pct": ausbeute_pct,
        "m_flaeche": m_flaeche, "m_test_flow": m_test_flow_effektiv, "m_test_druck": m_test_druck,
        "m_rueckhalt": m_rueckhalt, "tds_feed": tds_feed, "temp": temp, "p_system": p_system,
        "zuleitung_saug": saug_cfg, "zuleitung_druck": druck_cfg,
        "konz_leitungen": konz_zweige, "konz_out": konz_out,
        "perm_leitungen": perm_zweige, "perm_out": perm_out, "perm_schlauch": perm_schlauch
    }
    
    col_title, col_btn = st.columns([4, 1])
    with col_btn:
        pdf_bytes = generiere_pdf(inputs_fuer_pdf, ergebnisse)
        st.download_button("📄 PDF Export", data=pdf_bytes, file_name="ro_protokoll.pdf", mime="application/pdf")

    st.subheader("📊 Performance")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Permeat Gesamt", f"{ergebnisse['total_permeat']:.1f} l/h")
    c2.metric("Konzentrat Gesamt", f"{ergebnisse['end_konzentrat_flow']:.1f} l/h")
    c3.metric("Permeat TDS", f"{ergebnisse['total_permeat_tds']:.1f} ppm")
    c4.metric("Konz. TDS", f"{ergebnisse['final_konzentrat_tds']:.0f} ppm")

    st.dataframe(pd.DataFrame(ergebnisse['membran_daten']), use_container_width=True)
    
    st.divider()
    st.subheader("🛑 Hydraulik & Drossel")
    v1, v2, v3 = st.columns(3)
    
    if auslegungs_modus == "Drossel-Ø vorgeben (Digital Twin)":
        v1.metric("Pumpendruck (Real)", f"{ergebnisse.get('realer_pumpendruck', 0):.2f} bar")
        v3.metric("Drossel Ø (Fix)", f"Ø {drossel_vorgabe_mm:.2f} mm")
    else:
        v1.metric("Systemdruck (Vorgabe)", f"{p_system:.2f} bar")
        v3.metric("Empfohlener Drossel Ø", f"Ø {ergebnisse['empfohlene_drossel_mm']:.2f} mm")
        
    v2.metric("Druck vor Ventil", f"{ergebnisse['konzentrat_druck_verlauf']:.2f} bar")

    with st.expander("Detaillierte Druckverluste"):
        st.write(f"Druckverlust Saugseite: {ergebnisse['p_verlust_saug']:.3f} bar")
        st.write(f"Druckverlust Hauptleitung: {ergebnisse['p_verlust_druck_haupt']:.3f} bar")
        st.write(f"Effektiver Druck am Verzweigungspunkt: {ergebnisse['p_effektiv_start']:.2f} bar")
