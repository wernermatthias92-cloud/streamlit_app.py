import math
from membrane.modell import berechne_tcf, berechne_a_wert
from hydraulik.widerstand import berechne_hydraulischen_widerstand

def berechne_drossel_druckabfall(flow_lh, drossel_mm):
    if flow_lh <= 0.001 or drossel_mm <= 0: return 9999.0 
    q_ms = (flow_lh / 1000) / 3600
    area_m2 = math.pi * ((drossel_mm/1000) / 2)**2
    v_spalt = q_ms / (area_m2 * 0.6)
    return ((1000 * v_spalt**2) / 2) / 100000.0

def berechne_pumpendruck(flow_lh, p_max, q_max):
    if flow_lh >= q_max: return 0.0
    return p_max * (1.0 - (flow_lh / q_max)**2)

def simuliere_parallel_drossel(flow_fractions, membran_namen, drossel_vorgabe_mm, m_flaeche, m_test_flow,
                              m_test_druck, m_rueckhalt, tds_feed, temp, p_max, q_max, p_zulauf,
                              r_saug, r_druck_haupt, r_netzwerk, hat_t_stueck, 
                              leitungen_konz, leitung_out,
                              p_leitungen_konz, p_leitung_out, p_schlauch_out):
    
    tcf_real = berechne_tcf(temp)
    a_wert = berechne_a_wert(m_test_flow, m_flaeche, m_test_druck)

    # [Restliche Solver-Logik wie gehabt...]
    # ...
