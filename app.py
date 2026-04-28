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

# --- Lade Datenbanken ---
try:
    from utils.schlaeuche import SCHLAUCH_DATENBANK, get_schlauch_namen, get_schlauch_innen_d
    schlauch_namen = get_schlauch_namen()
except ImportError:
    SCHLAUCH_DATENBANK = {"Manuelle Eingabe": {"d_innen": 13.2, "d_aussen": 19.0, "info": ""}}
    schlauch_namen = ["Manuelle Eingabe"]
    def get_schlauch_innen_d(name): return 13.2

# --- 1. SESSION STATE INITIALISIERUNG ---
if 'p_flow_lh' not in st.session_state: st.session_state.p_flow_lh = 568.0
if 'p_flow_m3' not in st.session_state: st.session_state.p_flow_m3 = 13.63
if 'uploader_key' not in st.session_state: st.session_state.uploader_key = 0
if 'feed_us' not in st.session_state: st.session_state.feed_us = 160.0
if 'feed_ppm' not in st.session_state: st.session_state.feed_ppm = 96.0

def sync_m3(): st.session_state.p_flow_lh = st.session_state.p_flow_m3 * (1000 / 24)
def sync_lh(): st.session_state.p_flow_m3 = st.session_state.p_flow_lh * (24 / 1000)
def sync_ppm_to_us(): st.session_state.feed_us = st.session_state.feed_ppm / 0.6
def sync_us_to_ppm(): st.session_state.feed_ppm = st.session_state.feed_us * 0.6

def lade_profil_callback():
    aktueller_uploader_key = f"profil_uploader_{st.session_state.uploader_key}"
    if aktueller_uploader_key in st.session_state and st.session_state[aktueller_uploader_key] is not None:
        uploaded_file = st.session_state[aktueller_uploader_key]
        erfolg, msg = lade_konfiguration(uploaded_file)
        if erfolg:
            st.session_state.lade_msg = f"Konfiguration erfolgreich geladen! Aktuelle Konfiguration: **{uploaded_file.name}**"
            st.session_state.lade_erfolg = True
            st.session_state.uploader_key += 1
        else:
            st.session_state.lade_msg = msg
            st.session_state.lade_erfolg = False

# --- UI Helfer-Funktion für Schläuche ---
def render_schlauch_auswahl(label, key_base):
    auswahl = st.selectbox(label, schlauch_namen, key=f"{key_base}_sel")
    if auswahl == "Manuelle Eingabe":
        return st.number_input(f"Innen-Ø (mm)", min_value=0.01, value=13.2, step=0.1, key=f"{key_base}_val")
    else:
        d_innen = get_schlauch_innen_d(auswahl)
        st.caption(f"ℹ️ {SCHLAUCH_DATENBANK[auswahl]['info']} (Innen: {d_innen} mm)")
        return float(d_innen)

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
            drossel_vorgabe_mm = st.number_input("Fester Drossel-Ø (mm)", min_value=0.01, value=1.2, step=0.1, key="drossel_vorgabe_mm")
            ausbeute_pct = 0
    
    with st.expander("2. Membrane & System", expanded=True):
        st.markdown("**Datenblatt-Werte**")
        m_flaeche = st.number_input("Aktive Filterfläche (m²)", min_value=0.1, value=7.6, step=0.1, key="m_flaeche")
        
        c1, c2 = st.columns(2)
        with c1: st.number_input("Permeat Flow (l/h)", key='p_flow_lh', on_change=sync_lh)
        with c2: st.number_input("Permeat Flow (m³/d)", key='p_flow_m3', on_change=sync_m3)
            
        m_test_flow_effektiv = st.session_state.p_flow_lh * (1.0 + (st.number_input("Toleranz / Alterung (%)", min_value=-50.0, max_value=20.0, value=-5.0, step=1.0, key="m_toleranz_pct") / 100.0))
        
        cp, cr = st.columns(2)
        with cp: m_test_druck = st.number_input("Test-Druck (bar)", value=9.3, format="%.1f", step=0.1, key="m_test_druck")
        with cr: m_rueckhalt = st.number_input("Nominal Rejection (%)", min_value=0, max_value=100, value=98, step=1, key="m_rueckhalt_int") / 100.0
            
        m_test_tds = st.number_input("Test-Lösung (ppm NaCl)", value=500, step=50, key="m_test_tds")
        st.caption(f"💡 Entspricht Labor-Leitwert: **{m_test_tds / 0.5:.0f} µS/cm**")

        st.divider()
        st.markdown("**Reale Bedingungen**")
        
        u1, u2 = st.columns(2)
        with u1: st.number_input("Feed Leitwert (µS/cm)", key='feed_us', on_change=sync_us_to_ppm)
        with u2: st.number_input("Feed TDS (ppm)", key='feed_ppm', on_change=sync_ppm_to_us)
            
        tds_feed = st.session_state.feed_ppm
        temp = st.slider("Wassertemperatur real (°C)", 1, 50, 13, key="temp")
        trocken_modus = st.checkbox("Auslieferzustand: Trocken (Dry Membrane)", value=False, key="trocken_modus")
        
        st.divider()
        if auslegungs_modus == "Ziel-Ausbeute vorgeben":
            p_system = st.number_input("Systemdruck nach Pumpe (bar)", value=9.4, step=0.1, format="%.1f", key="p_system_ziel")
            pump_cfg = {"mode": None, "p_max": 0, "q_max": 0, "p_fix": p_system, "p_z": 0, "exp": 2.0}
        else:
            pump_mode = st.radio("Druck-Ermittlung", ["Manometer", "Kennlinie"])
            p_z = st.number_input("Zulaufdruck (bar)", value=3.0)
            
            if pump_mode == "Manometer":
                p_fix = st.number_input("Manometerdruck (bar)", value=9.4)
                pump_cfg = {"mode": "Manometer", "p_max": 0, "q_max": 0, "p_fix": p_fix, "p_z": p_z, "exp": 2.0}
            else:
                try:
                    from utils.pumpen import PUMPEN_DATENBANK, get_pumpen_namen
                    pumpen_namen = get_pumpen_namen()
                except ImportError:
                    PUMPEN_DATENBANK = {"Manuelle Eingabe": {"p_max": 11.5, "q_max": 1920.0, "exponent": 2.0, "info": ""}}
                    pumpen_namen = ["Manuelle Eingabe"]
                    
                pumpen_auswahl = st.selectbox("Pumpe wählen", pumpen_namen)
                if pumpen_auswahl == "Manuelle Eingabe":
                    p_max = st.number_input("Max. Druck (bar)", value=11.5)
                    q_max = st.number_input("Max. Flow (l/h)", value=1920.0)
                    pump_exp = st.slider("Pumpen-Exponent", 1.5, 4.0, 2.0, step=0.1)
                else:
                    db_pumpe = PUMPEN_DATENBANK[pumpen_auswahl]
                    p_max, q_max, pump_exp = db_pumpe["p_max"], db_pumpe["q_max"], db_pumpe["exponent"]
                    st.success(f"**{pumpen_auswahl} geladen**\n\nMax: {p_max} bar | {q_max} l/h | Exp: {pump_exp}")
                    st.caption(db_pumpe["info"])
                    
                pump_cfg = {"mode": "Kennlinie", "p_max": p_max, "q_max": q_max, "p_z": p_z, "exp": pump_exp}

    with st.expander("3. Zuleitung & T-Stücke", expanded=False):
        if auslegungs_modus == "Drossel-Ø vorgeben (Digital Twin)" and pump_cfg["mode"] == "Manometer":
            st.info("💡 Saugseite & Zulaufdruck werden ignoriert, da der echte Druck bereits NACH der Pumpe gemessen wurde.")
            saug_cfg = {"d": 13.2, "l": 0.0, "b": 0}
        else:
            st.markdown("**Saugseite**")
            saug_cfg = {
                "d": render_schlauch_auswahl("Schlauch Saugseite", "ds"),
                "l": st.number_input("Länge Saug (mm)", min_value=0.01, value=1000.0, step=5.0, key="ls"),
                "b": st.number_input("Bögen Saug", min_value=0, max_value=20, value=0, key="bs")
            }
            
        st.markdown("**Druckseite (Hauptleitung)**")
        druck_cfg = {
            "d": render_schlauch_auswahl("Schlauch Hauptleitung", "dh"),
            "l": st.number_input("Länge Haupt (mm)", min_value=0.01, value=400.0, step=5.0, key="lh"),
            "b": st.number_input("Bögen Haupt", min_value=0, max_value=20, value=0, key="bh")
        }
        
        st.divider()
        hat_t_stueck = st.checkbox("Hauptleitung durch T-Stück aufteilen", value=False, key="hat_t_stueck")
        netzwerk_cfg = {"hat_t_stueck": hat_t_stueck}
        
        if hat_t_stueck:
            colA, colB = st.columns(2)
            with colA:
                st.markdown("Strang A")
                netzwerk_cfg.update({
                    "d_a": render_schlauch_auswahl("Schlauch A", "d_a"), 
                    "l_a": st.number_input("L A", min_value=0.01, value=150.0, step=5.0, key="l_a"), 
                    "b_a": st.number_input("B A", min_value=0, value=1, key="b_a")
                })
                sub_a = st.checkbox("A aufteilen", key="sub_a")
                netzwerk_cfg.update({"sub_a": sub_a, "d_a1": 0, "l_a1": 0, "b_a1": 0, "d_a2": 0, "l_a2": 0, "b_a2": 0})
                if sub_a:
                    netzwerk_cfg.update({
                        "d_a1": render_schlauch_auswahl("Schlauch A1", "d_a1"), 
                        "l_a1": st.number_input("L A1", min_value=0.01, value=500.0, step=5.0, key="l_a1"), "b_a1": 0,
                        "d_a2": render_schlauch_auswahl("Schlauch A2", "d_a2"), 
                        "l_a2": st.number_input("L A2", min_value=0.01, value=500.0, step=5.0, key="l_a2"), "b_a2": 0
                    })
            with colB:
                st.markdown("Strang B")
                netzwerk_cfg.update({
                    "d_b": render_schlauch_auswahl("Schlauch B", "d_b"), 
                    "l_b": st.number_input("L B", min_value=0.01, value=150.0, step=5.0, key="l_b"), 
                    "b_b": st.number_input("B B", min_value=0, value=1, key="b_b")
                })
                sub_b = st.checkbox("B aufteilen", value=False, key="sub_b")
                netzwerk_cfg.update({"sub_b": sub_b, "d_b1": 0, "l_b1": 0, "b_b1": 0, "d_b2": 0, "l_b2": 0, "b_b2": 0})
                if sub_b:
                    netzwerk_cfg.update({
                        "d_b1": render_schlauch_auswahl("Schlauch B1", "d_b1"), 
                        "l_b1": st.number_input("L B1", min_value=0.01, value=200.0, step=5.0, key="l_b1"), "b_b1": 0,
                        "d_b2": render_schlauch_auswahl("Schlauch B2", "d_b2"), 
                        "l_b2": st.number_input("L B2", min_value=0.01, value=200.0, step=5.0, key="l_b2"), "b_b2": 0
                    })
        else:
            netzwerk_cfg.update({"d_a": 0, "l_a": 0, "b_a": 0, "sub_a": False, "d_a1": 0, "l_a1": 0, "b_a1": 0, "d_a2": 0, "l_a2": 0, "b_a2": 0,
                                 "d_b": 0, "l_b": 0, "b_b": 0, "sub_b": False, "d_b1": 0, "l_b1": 0, "b_b1": 0, "d_b2": 0, "l_b2": 0, "b_b2": 0})

    _, m_namen, _ = berechne_feed_widerstaende(**netzwerk_cfg)
    anzahl_membranen = len(m_namen)

    with st.expander("4. Konzentratleitungen", expanded=False):
        konz_zweige = []
        for i in range(anzahl_membranen):
            konz_zweige.append({
                "d": render_schlauch_auswahl(f"Schlauch Konz {m_namen[i]}", f"kd_{i}"), 
                "l": st.number_input(f"Länge Konz {i} (mm)", min_value=0.01, value=100.0, step=5.0, key=f"kl_{i}"), 
                "b": 0
            })
        st.divider()
        konz_out = {
            "d": render_schlauch_auswahl("Sammelrohr Konz", "kod"), 
            "l": st.number_input("Länge Sammel Konz (mm)", min_value=0.01, value=300.0, step=5.0, key="kol"), 
            "b": 2
        }

    with st.expander("5. Permeatleitungen", expanded=False):
        perm_zweige = []
        for i in range(anzahl_membranen):
            perm_zweige.append({
                "d": render_schlauch_auswahl(f"Schlauch Perm {m_namen[i]}", f"pd_{i}"), 
                "l": st.number_input(f"Länge Perm {i} (mm)", min_value=0.01, value=300.0, step=5.0, key=f"pl_{i}"), 
                "b": st.number_input(f"Bögen Perm {i} (0=Y-Stück)", min_value=0, max_value=20, value=0, key=f"pb_{i}")
            })
        st.divider()
        perm_out = {
            "d": render_schlauch_auswahl("Sammelrohr Perm", "pod"), 
            "l": st.number_input("Länge Sammel Perm (mm)", min_value=0.01, value=1000.0, step=5.0, key="pol"), 
            "b": st.number_input("Bögen Sammel Perm", min_value=0, max_value=20, value=0, key="pob")
        }
        st.divider()
        st.markdown("**Auslassschlauch**")
        perm_schlauch = {
            "d": render_schlauch_auswahl("Auslassschlauch", "psd"),
            "l": st.number_input("Länge Schlauch (mm)", min_value=0.01, value=1.0, step=5.0, key="psl"),
            "h": st.number_input("Höhendifferenz Austritt (m)", value=0.0, step=0.5, key="psh")
        }

# --- 3. BERECHNUNGSLOGIK DREIFACH AUSFÜHREN ---
hydraulik = analysiere_gesamte_topologie(saug_cfg, druck_cfg, netzwerk_cfg, konz_zweige, konz_out, perm_zweige, perm_out, perm_schlauch)

tol = 0.18
m_test_flow_min = m_test_flow_effektiv * (1 - tol)
m_test_flow_max = m_test_flow_effektiv * (1 + tol)

if auslegungs_modus == "Ziel-Ausbeute vorgeben":
    ergebnisse_ideal = simuliere_parallel(hydraulik, ausbeute_pct, m_flaeche, m_test_flow_effektiv, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, pump_cfg.get("p_fix", 0))
    ergebnisse_min = simuliere_parallel(hydraulik, ausbeute_pct, m_flaeche, m_test_flow_min, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, pump_cfg.get("p_fix", 0))
    ergebnisse_max = simuliere_parallel(hydraulik, ausbeute_pct, m_flaeche, m_test_flow_max, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, pump_cfg.get("p_fix", 0))
else:
    ergebnisse_ideal = simuliere_parallel_drossel(hydraulik, drossel_vorgabe_mm, m_flaeche, m_test_flow_effektiv, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, pump_cfg["mode"], pump_cfg["p_max"], pump_cfg["q_max"], pump_cfg["p_z"], pump_cfg.get("p_fix", 0), pump_cfg["exp"])
    ergebnisse_min = simuliere_parallel_drossel(hydraulik, drossel_vorgabe_mm, m_flaeche, m_test_flow_min, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, pump_cfg["mode"], pump_cfg["p_max"], pump_cfg["q_max"], pump_cfg["p_z"], pump_cfg.get("p_fix", 0), pump_cfg["exp"])
    ergebnisse_max = simuliere_parallel_drossel(hydraulik, drossel_vorgabe_mm, m_flaeche, m_test_flow_max, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, trocken_modus, pump_cfg["mode"], pump_cfg["p_max"], pump_cfg["q_max"], pump_cfg["p_z"], pump_cfg.get("p_fix", 0), pump_cfg["exp"])

ergebnisse = ergebnisse_ideal 

# --- 4. MAIN WINDOW ---
col_title, col_btn = st.columns([3, 1])

with col_title: st.title("💧 RO-Anlagen Planer")

with col_btn:
    st.write("") 
    with st.expander("💾 Profil Speichern / Laden", expanded=False):
        dynamischer_uploader_key = f"profil_uploader_{st.session_state.uploader_key}"
        st.file_uploader("Profil laden (.json)", type=["json"], key=dynamischer_uploader_key, label_visibility="collapsed")
        st.button("Laden", use_container_width=True, on_click=lade_profil_callback)
        
        if "lade_msg" in st.session_state:
            if st.session_state.lade_erfolg: st.success(st.session_state.lade_msg)
            else: st.error(st.session_state.lade_msg)
            del st.session_state.lade_msg
            del st.session_state.lade_erfolg
                    
        st.divider()
        wunsch_dateiname = st.text_input("Dateiname", value="ro_anlagen_profil")
        if not wunsch_dateiname.endswith(".json"): wunsch_dateiname += ".json"
            
        verbotene_keys = ["lade_msg", "lade_erfolg", "uploader_key"]
        aktuelle_konfig = {k: v for k, v in st.session_state.items() if not k.startswith('_') and k not in verbotene_keys and not k.startswith("profil_uploader")}
        json_string = exportiere_konfiguration(aktuelle_konfig)
        st.download_button(label="Als .json exportieren", data=json_string, file_name=wunsch_dateiname, mime="application/json", use_container_width=True)

if auslegungs_modus == "Drossel-Ø vorgeben (Digital Twin)" and pump_cfg["mode"] == "Manometer":
    st.warning("⚠️ **Physikalischer Hinweis:** Du hast den Systemdruck fixiert (Manometer-Modus). Wenn du jetzt den Drosseldurchmesser änderst, rechnet das Programm mit einer *unendlich starken Pumpe*, die diesen Druck zwingend aufrecht erhält. Der Konzentratstrom wird dadurch massiv ansteigen, aber das Permeat bleibt konstant! Um den realen Druck- und Permeateinbruch beim Öffnen der Drossel zu simulieren, stelle den Modus in der Sidebar bitte auf **'Kennlinie'** um.")

if ergebnisse.get("error"):
    st.error(ergebnisse["error"])
else:
    p_ideal, p_min, p_max = ergebnisse_ideal.get('total_permeat', 0), ergebnisse_min.get('total_permeat', 0), ergebnisse_max.get('total_permeat', 0)
    k_ideal, k_min, k_max = ergebnisse_ideal.get('end_konzentrat_flow', 0), ergebnisse_min.get('end_konzentrat_flow', 0), ergebnisse_max.get('end_konzentrat_flow', 0)
    ptds_ideal, ptds_min, ptds_max = ergebnisse_ideal.get('total_permeat_tds', 0), ergebnisse_min.get('total_permeat_tds', 0), ergebnisse_max.get('total_permeat_tds', 0)
    ktds_ideal, ktds_min, ktds_max = ergebnisse_ideal.get('final_konzentrat_tds', 0), ergebnisse_min.get('final_konzentrat_tds', 0), ergebnisse_max.get('final_konzentrat_tds', 0)

    inputs_fuer_pdf = {
        "schaltung": schaltung, "anzahl_membranen": anzahl_membranen, "ausbeute_pct": ausbeute_pct,
        "m_flaeche": m_flaeche, "m_test_flow": m_test_flow_effektiv, "m_test_druck": m_test_druck,
        "m_rueckhalt": m_rueckhalt, "tds_feed": tds_feed, "temp": temp, "trocken_modus": trocken_modus, "p_system": pump_cfg.get("p_fix", 0),
        "zuleitung_saug": saug_cfg, "zuleitung_druck": druck_cfg,
        "konz_leitungen": konz_zweige, "konz_out": konz_out,
        "perm_leitungen": perm_zweige, "perm_out": perm_out, "perm_schlauch": perm_schlauch
    }
    
    with col_btn:
        st.write("") 
        pdf_bytes = generiere_pdf(inputs_fuer_pdf, ergebnisse)
        st.download_button("📄 PDF Export", data=pdf_bytes, file_name="ro_protokoll.pdf", mime="application/pdf", use_container_width=True)

    st.subheader("📊 Performance & Leitwerte (±18%)")
    if trocken_modus: st.info("🏜️ **Trocken-Modus aktiv:** Permeabilität wurde um +15 % erhöht, nomineller Rückhalt um -2,5 % reduziert.")
    
    h1, h2, h3, h4 = st.columns([2, 1, 1, 1])
    h2.markdown("**Minimum (-18%)**")
    h3.markdown("**Idealwert**")
    h4.markdown("**Maximum (+18%)**")
    st.divider()

    def perf_row(label, v_min, v_ideal, v_max, unit, precision=1):
        r1, r2, r3, r4 = st.columns([2, 1, 1, 1])
        r1.markdown(f"**{label}**")
        r2.write(f"{v_min:.{precision}f} {unit}")
        r3.write(f"**{v_ideal:.{precision}f} {unit}**")
        r4.write(f"{v_max:.{precision}f} {unit}")
        
    def us_ppm(ppm): return f"{ppm/0.6:.1f} µS/cm ({ppm:.1f} ppm)"

    perf_row("Permeatfluss", p_min, p_ideal, p_max, "l/h")
    perf_row("Konzentratfluss", k_min, k_ideal, k_max, "l/h")
    
    col_l, col1, col2, col3 = st.columns([2, 1, 1, 1])
    col_l.markdown("**Permeat Qualität**")
    col1.write(us_ppm(ptds_min))
    col2.write(f"**{us_ppm(ptds_ideal)}**")
    col3.write(us_ppm(ptds_max))

    col_l, col1, col2, col3 = st.columns([2, 1, 1, 1])
    col_l.markdown("**Konzentrat Qualität**")
    col1.write(us_ppm(ktds_min))
    col2.write(f"**{us_ppm(ktds_ideal)}**")
    col3.write(us_ppm(ktds_max))
    
    st.divider()
    st.dataframe(pd.DataFrame(ergebnisse['membran_daten']), use_container_width=True)
    st.caption("💡 **Flux Info:** Ein Flux zwischen 15-25 LMH gilt bei Brunnenwasser als konservativ/sicher.")
    
    st.divider()
    st.subheader("🛡️ Sicherheits-Check & Hydraulik")
    dp = ergebnisse.get('max_spacer_dp', 0)
    
    if dp > 1.03: st.error(f"⚠️ **KRITISCHER DRUCKVERLUST:** {dp:.2f} bar. Der maximale Druckverlust von 1,03 bar wurde überschritten! (Gefahr von Telescoping)")
    elif dp > 0.8: st.warning(f"🔔 **Hoher Druckverlust:** {dp:.2f} bar. Du näherst dich dem Limit von 1,03 bar.")
    else: st.success(f"✅ **Druckverlust Spacer:** {dp:.2f} bar (Limit: 1,03 bar)")
        
    st.write("")
    v1, v2, v3 = st.columns(3)
    
    if auslegungs_modus == "Drossel-Ø vorgeben (Digital Twin)":
        if pump_cfg["mode"] == "Manometer": v1.metric("Pumpendruck (Fix)", f"{pump_cfg.get('p_fix', 0):.2f} bar")
        else: v1.metric("Pumpendruck (Real)", f"{ergebnisse.get('realer_pumpendruck', 0):.2f} bar")
        v3.metric("Drossel Ø (Fix)", f"Ø {drossel_vorgabe_mm:.2f} mm")
    else:
        v1.metric("Systemdruck (Vorgabe)", f"{pump_cfg.get('p_fix', 0):.2f} bar")
        v3.metric("Empfohlener Drossel Ø", f"Ø {ergebnisse['empfohlene_drossel_mm']:.2f} mm")
        
    v2.metric("Druck vor Ventil", f"{ergebnisse['konzentrat_druck_verlauf']:.2f} bar")

    with st.expander("Detaillierte Druckverluste"):
        st.write(f"Druckverlust Saugseite: {ergebnisse['p_verlust_saug']:.3f} bar")
        st.write(f"Druckverlust Hauptleitung: {ergebnisse['p_verlust_druck_haupt']:.3f} bar")
        st.write(f"Effektiver Druck am Verzweigungspunkt: {ergebnisse['p_effektiv_start']:.2f} bar")
