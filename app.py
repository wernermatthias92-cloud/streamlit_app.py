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

# ... (Session State & Callbacks identisch)

# --- (SIDEBAR identisch bis zur Berechnung) ---
# [Sidebar Code hier einfügen...]

# --- BERECHNUNGSLOGIK ---
hydraulik = analysiere_gesamte_topologie(saug_cfg, druck_cfg, netzwerk_cfg, konz_zweige, konz_out, perm_zweige, perm_out, perm_schlauch)

if auslegungs_modus == "Ziel-Ausbeute vorgeben":
    ergebnisse = simuliere_parallel(hydraulik, ausbeute_pct, m_flaeche, m_test_flow_effektiv, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, p_system)
else:
    ergebnisse = simuliere_parallel_drossel(hydraulik, drossel_vorgabe_mm, m_flaeche, m_test_flow_effektiv, m_test_druck, m_test_tds, m_rueckhalt, tds_feed, temp, pumpen_modus, pumpe_p_max, pumpe_q_max, p_zulauf, p_fix)

# --- MAIN WINDOW ---
col_title, col_btn = st.columns([3, 1])
with col_title: st.title("💧 RO-Anlagen Planer")
# [Speicher/Laden & PDF Buttons hier einfügen...]

if ergebnisse.get("error"):
    st.error(ergebnisse["error"])
else:
    # --- TOLERANZ-BERECHNUNG (+-18%) ---
    tol = 0.18
    p_ideal = ergebnisse['total_permeat']
    k_ideal = ergebnisse['end_konzentrat_flow']
    f_total = ergebnisse['q_feed_start_lh']
    
    # Flows
    p_min, p_max = p_ideal * (1-tol), p_ideal * (1+tol)
    k_at_pmin, k_at_pmax = f_total - p_min, f_total - p_max
    
    # TDS Schätzung (Mass Balance)
    # Annahme: Salzdurchgang bleibt prozentual ähnlich, aber Konzentration im System ändert sich durch Recovery
    def calc_tds_range(p_flow, k_flow):
        if p_flow + k_flow <= 0: return 0, 0
        # Reale Recovery an diesem Punkt
        rec = p_flow / (p_flow + k_flow)
        # Konzentrationsfaktor
        cf = 1 / (1 - rec) if rec < 1 else 10
        # Permeat TDS (Grob-Approximation über CF)
        p_tds = ergebnisse['total_permeat_tds'] * (cf / (1/(1-(p_ideal/f_total))))
        # Konz TDS
        k_tds = (f_total * tds_feed - p_flow * p_tds) / k_flow if k_flow > 0 else tds_feed * cf
        return p_tds, k_tds

    ptds_at_pmin, ktds_at_pmin = calc_tds_range(p_min, k_at_pmin)
    ptds_at_pmax, ktds_at_pmax = calc_tds_range(p_max, k_at_pmax)

    # --- PERFORMANCE ANZEIGE (VERTIKAL MIT TOLERANZ) ---
    st.subheader("📊 Performance & Toleranzen (±18%)")
    
    # Header Zeile
    h1, h2, h3, h4 = st.columns([2, 1, 1, 1])
    h2.markdown("**Minimum (-18%)**")
    h3.markdown("**Idealwert**")
    h4.markdown("**Maximum (+18%)**")
    st.divider()

    # Zeilenweise Performance
    def perf_row(label, v_min, v_ideal, v_max, unit, precision=1):
        r1, r2, r3, r4 = st.columns([2, 1, 1, 1])
        r1.markdown(f"**{label}**")
        r2.write(f"{v_min:.{precision}f} {unit}")
        r3.write(f"**{v_ideal:.{precision}f} {unit}**")
        r4.write(f"{v_max:.{precision}f} {unit}")

    perf_row("Permeatfluss", p_min, p_ideal, p_max, "l/h")
    perf_row("Konzentratfluss", k_at_pmin, k_ideal, k_at_pmax, "l/h")
    perf_row("Permeat TDS", ptds_at_pmin, ergebnisse['total_permeat_tds'], ptds_at_pmax, "ppm", 1)
    perf_row("Konzentrat TDS", ktds_at_pmin, ergebnisse['final_konzentrat_tds'], ktds_at_pmax, "ppm", 0)
    
    st.divider()
    st.dataframe(pd.DataFrame(ergebnisse['membran_daten']), use_container_width=True)
    
    # --- SICHERHEITS-CHECK (Delta P) ---
    st.subheader("🛡️ Sicherheits-Check & Hydraulik")
    dp = ergebnisse['max_spacer_dp']
    
    if dp > 1.03:
        st.error(f"⚠️ **KRITISCHER DRUCKVERLUST:** {dp:.2f} bar. Der maximale Druckverlust von 1,03 bar wurde überschritten! (Gefahr von Telescoping)")
    elif dp > 0.8:
        st.warning(f"🔔 **Hoher Druckverlust:** {dp:.2f} bar. Du näherst dich dem Limit von 1,03 bar.")
    else:
        st.success(f"✅ **Druckverlust Spacer:** {dp:.2f} bar (Limit: 1,03 bar)")

    v1, v2, v3 = st.columns(3)
    # [Rest der Hydraulik-Metriken wie vorher...]
