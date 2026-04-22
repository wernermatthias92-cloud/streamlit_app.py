import streamlit as st
import pandas as pd
import math

# Eigene Module laden
from hydraulik.widerstand import berechne_hydraulischen_widerstand
from system.parallel import simuliere_parallel
from system.parallel_drossel import simuliere_parallel_drossel
from hydraulik.netzwerk import analysiere_gesamte_topologie, berechne_feed_widerstaende
from utils.pdf_export import generiere_pdf
from utils.konfiguration import exportiere_konfiguration, lade_konfiguration

st.set_page_config(page_title="RO-Anlagen Planer Pro", layout="wide")

# --- 1. SESSION STATE INITIALISIERUNG ---
if 'p_flow_lh' not in st.session_state:
    st.session_state.p_flow_lh = 568.0
if 'p_flow_m3' not in st.session_state:
    st.session_state.p_flow_m3 = 13.63
# NEU: Ein Zähler, um den Uploader nach dem Laden zurückzusetzen
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

def sync_m3():
    st.session_state.p_flow_lh = st.session_state.p_flow_m3 * (1000 / 24)
def sync_lh():
    st.session_state.p_flow_m3 = st.session_state.p_flow_lh * (24 / 1000)

# --- CALLBACK FÜR DAS LADEN DES PROFILS ---
def lade_profil_callback():
    # Wir rufen den Uploader über seinen dynamischen Key auf
    aktueller_uploader_key = f"profil_uploader_{st.session_state.uploader_key}"
    if aktueller_uploader_key in st.session_state and st.session_state[aktueller_uploader_key] is not None:
        uploaded_file = st.session_state[aktueller_uploader_key]
        erfolg, msg = lade_konfiguration(uploaded_file)
        
        if erfolg:
            # NEU: Eigene Erfolgsmeldung mit Dateinamen
            st.session_state.lade_msg = f"Konfiguration erfolgreich geladen! Aktuelle Konfiguration: **{uploaded_file.name}**"
            st.session_state.lade_erfolg = True
            # NEU: Den Uploader-Key hochzählen, damit das Feld geleert wird!
            st.session_state.uploader_key += 1
        else:
            st.session_state.lade_msg = msg
            st.session_state.lade_erfolg = False

# --- 2. SIDEBAR EINGABEN ---
with st.sidebar:
    st.title("⚙️ Parameter")
    
    with st.expander("1. Verschaltung & Modus", expanded=True):
        st.info("🔧 Modus: Parallele Verschaltung")
        schaltung = "Parallel (Aufteilung)"
        
        auslegungs_modus = st.radio("Auslegungs-Modus", ["Ziel-Ausbeute vorgeben", "Drossel-Ø vorgeben (Digital Twin)"], key="auslegungs_modus")
        
        if auslegungs_modus == "Ziel-Ausbeute vorgeben":
            ausbeute_pct = st.slider("Ziel-Ausbeute Anlage (%)", 5, 90, 50, key="ausbeute_pct")
            drossel_vorgabe_mm = 0
        else:
            drossel_vorgabe_mm = st.number_input("Fester Drossel-Ø (mm)", min_value=0.1, value=1.2, step=0.1, key="drossel_vorgabe_mm")
            ausbeute_pct = 0
    
    with st.expander("2. Membrane & System", expanded=True):
        st.markdown("**Datenblatt-Werte**")
        m_flaeche = st.number_input("Aktive Filterfläche (m²)", min_value=0.1, value=7.6, step=0.1, key="m_flaeche")
        
        c1, c2 = st.columns(2)
        with c1:
            st.number_input("Permeat Flow (l/h)", key='p_flow_lh', on_change=sync_lh)
        with c2:
            st.number_input("Permeat Flow (m³/d)", key='p_flow_m3', on_change=sync_m3)
            
        m_test_flow_datasheet = st.session_state.p_flow_lh
        m_toleranz_pct = st.number_input("Toleranz / Alterung (%)", min_value=-50.0, max_value=20.0, value=-5.0, step=1.0, key="m_toleranz_pct")
        m_test_flow_effektiv = m_test_flow_datasheet * (1.0 + (m_toleranz_pct / 100.0))
        
        cp, cr = st.columns(2)
        with cp:
            m_test_druck = st.number_input("Test-Druck (bar)", value=9.3, format="%.1f", step=0.1, key="m_test_druck")
        with cr:
            m_rueckhalt_int = st.number_input("Nominal Rejection (%)", min_value=0, max_value=100, value=98, step=1, key="m_rueckhalt_int")
            m_rueckhalt = m_rueckhalt_int / 100.0
            
        m_test_tds = st.number_input("Test-Lösung (ppm NaCl)", value=500, step=50, key="m_test_tds")

        st.divider()
        st.markdown("**Reale Bedingungen**")
        tds_feed = st.number_input("Feed TDS real (ppm)", value=96, key="tds_feed")
        temp = st.slider("Wassertemperatur real (°C)", 1, 50, 13, key="temp")
        
        st.divider()
        if auslegungs_modus == "Ziel-Ausbeute vorgeben":
            p_system = st.number_input("Systemdruck nach Pumpe (bar)", value=9.4, step=0.1, format="%.1f", key="p_system_ziel")
            pumpen_modus, pumpe_p_max, pumpe_q_max, p_fix = None, 0, 0, p_system
        else:
            pumpen_modus = st.radio("Pumpendruck-Ermittlung", ["Gemessenen Druck eintragen (Manometer)", "Pumpenkennlinie berechnen"], key="pumpen_modus")
            if pumpen_modus == "Gemessenen Druck eintragen (Manometer)":
                p_fix = st.number_input("Manometerdruck nach Pumpe (bar)", value=9.4, step=0.1, format="%.1f", key="p_fix")
                pumpe_p_max, pumpe_q_max = 0, 0
                p_system = p_fix
            else:
                p_fix = 0
                pumpe_p_max = st.number_input("Max. Druck bei 0 l/h (bar)", value=11.5, step=0.5, format="%.1f", key="pumpe_p_max")
                pumpe_q_max = st.number_input("Max. Durchfluss bei 0 bar (l/h)", value=2500.0, step=100.0, key="pumpe_q_max")
                p_system = pumpe_p_max

    with st.expander("3. Zuleitung & T-Stücke", expanded=False):
        if auslegungs_modus == "Drossel-Ø vorgeben (Digital Twin)" and pumpen_modus == "Gemessenen Druck eintragen (Manometer)":
            st.info("💡 Saugseite & Zulaufdruck werden ignoriert, da der echte Druck bereits NACH der Pumpe gemessen wurde.")
            p_zulauf = 0.0
            saug_cfg = {"d": 13.2, "l": 0.0, "b": 0}
        else:
            p_zulauf = st.number_input("Zulaufdruck Ruhezustand (bar)", value=3.0, step=0.1, key="pz")
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
        hat_t_stueck = st.checkbox("Hauptleitung durch T-Stück aufteilen", value=True, key="hat_t_stueck")
        
        netzwerk_cfg = {"hat_t_stueck": hat_t_stueck}
        if hat_t_stueck:
            colA, colB = st.columns(2)
            with colA:
                st.markdown("Strang A")
                netzwerk_cfg.update({"d_a": st.number_input("Ø A", 13.2, key="d_a"), "l_a": st.number_input("L A", 150.0, key="l_a"), "b_a": st.number_input("B A", 1, key="b_a")})
                sub_a = st.checkbox("A aufteilen", key="sub_a")
                netzwerk_cfg.update({"sub_a": sub_a, "d_a1": 0, "l_a1": 0, "b_a1": 0, "d_a2": 0, "l_a2": 0, "b_a2": 0})
                if sub_a:
                    netzwerk_cfg.update({"d_a1": st.number_input("Ø A1", 10.0, key="d_a1"), "l_a1": st.number_input("L A1", 500.0, key="l_a1"), "b_a1": 0,
                                        "d_a2": st.number_input("Ø A2", 10.0, key="d_a2"), "l_a2": st.number_input("L A2", 500.0, key="l_a2"), "b_a2": 0})
            with colB:
                st.markdown("Strang B")
                netzwerk_cfg.update({"d_b": st.number_input("Ø B", 13.2, key="d_b"), "l_b": st.number_input("L B", 150.0, key="l_b"), "b_b": st.number_input("B B", 1, key="b_b")})
                sub_b = st.checkbox("B aufteilen", value=True, key="sub_b")
                netzwerk_cfg.update({"sub_b": sub_b, "d_b1": 0, "l_b1": 0, "b_b1": 0, "d_b2": 0, "l_b2": 0, "b_b2": 0})
                if sub_b:
                    netzwerk_cfg.update({"d_b1": st.number_input("Ø B1", 13.2, key="d_b1"), "l_b1": st.number_input("L B1", 200.0, key="l_b1"), "b_b1": 0,
                                        "d_b2": st.number_input("Ø B2", 13.2, key="d_b2"), "l_b2": st.number_input("L B2", 200.0, key="l_b2"), "b_b2": 0})
        else:
            netzwerk_cfg.update({"d_a": 0, "l_a": 0, "b_a": 0, "sub_a": False, "d_a1": 0, "l_a1": 0, "b_a1": 0, "d_a2": 0, "l_a2": 0, "b_a2": 0,
                                 "d_b": 0, "l_b": 0, "b_b": 0, "sub_b": False, "d_b1": 0, "l_b1": 0, "b_b1": 0, "d_b2": 0, "l_b2": 0, "b_b2": 0})

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
        m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, 
        pumpen_modus, pumpe_p_max, pumpe_q_max, p_zulauf, p_fix
    )

# --- 4. MAIN WINDOW ---
col_title, col_btn = st.columns([3, 1])

with col_title:
    st.title("💧 RO-Anlagen Planer")

with col_btn:
    st.write("") # Spacer
    with st.expander("💾 Profil Speichern / Laden", expanded=False):
        # NEU: Der Uploader bekommt einen dynamischen Key (z.B. profil_uploader_0, dann _1, etc.)
        dynamischer_uploader_key = f"profil_uploader_{st.session_state.uploader_key}"
        st.file_uploader("Profil laden (.json)", type=["json"], key=dynamischer_uploader_key, label_visibility="collapsed")
        
        st.button("Laden", use_container_width=True, on_click=lade_profil_callback)
        
        # Erfolgsmeldung inkl. Dateiname anzeigen
        if "lade_msg" in st.session_state:
            if st.session_state.lade_erfolg:
                st.success(st.session_state.lade_msg)
            else:
                st.error(st.session_state.lade_msg)
            del st.session_state.lade_msg
            del st.session_state.lade_erfolg
                    
        st.divider()
        
        # NEU: Textfeld für den Dateinamen beim Export
        wunsch_dateiname = st.text_input("Dateiname", value="ro_anlagen_profil")
        if not wunsch_dateiname.endswith(".json"):
            wunsch_dateiname += ".json"
            
        verbotene_keys = ["lade_msg", "lade_erfolg", "uploader_key"]
        # Alle Variablen, die mit profil_uploader anfangen, werden ebenfalls gefiltert
        aktuelle_konfig = {k: v for k, v in st.session_state.items() if not k.startswith('_') and k not in verbotene_keys and not k.startswith("profil_uploader")}
        json_string = exportiere_konfiguration(aktuelle_konfig)
        
        st.download_button(
            label="Als .json exportieren",
            data=json_string,
            file_name=wunsch_dateiname, # Wendet den Wunschnamen an
            mime="application/json",
            use_container_width=True
        )

if ergebnisse.get("error"):
    st.error(ergebnisse["error"])
else:
    inputs_fuer_pdf = {
        "schaltung": schaltung, "anzahl_membranen": anzahl_membranen, "ausbeute_pct": ausbeute_pct,
        "m_flaeche": m_flaeche, "m_test_flow": m_test_flow_effektiv, "m_test_druck": m_test_druck,
        "m_rueckhalt": m_rueckhalt, "tds_feed": tds_feed, "temp": temp, "p_system": p_system,
        "zuleitung_saug": saug_cfg, "zuleitung_druck": druck_cfg,
        "konz_leitungen": konz_zweige, "konz_out": konz_out,
        "perm_leitungen": perm_zweige, "perm_out": perm_out, "perm_schlauch": perm_schlauch
    }
    
    with col_btn:
        st.write("") 
        pdf_bytes = generiere_pdf(inputs_fuer_pdf, ergebnisse)
        st.download_button("📄 PDF Export", data=pdf_bytes, file_name="ro_protokoll.pdf", mime="application/pdf", use_container_width=True)

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
        if pumpen_modus == "Gemessenen Druck eintragen (Manometer)":
            v1.metric("Pumpendruck (Fix)", f"{p_fix:.2f} bar")
        else:
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
