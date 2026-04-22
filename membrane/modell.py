import math

def berechne_tcf(temp_c):
    """Berechnet den Temperaturkorrekturfaktor (TCF)."""
    return math.exp(2640 * (1/298.15 - 1/(temp_c + 273.15)))

def berechne_a_wert(m_test_flow, m_flaeche, m_test_druck):
    """Berechnet die Permeabilität (A-Wert) der Membran."""
    # 1500 ppm NaCl entsprechen grob 1.05 bar osmotischem Druck
    pi_test = (1500 / 100) * 0.07 
    return (m_test_flow / 1000) / (m_flaeche * (m_test_druck - pi_test))
