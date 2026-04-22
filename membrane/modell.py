import math

def berechne_tcf(temp_c):
    """Berechnet den Temperaturkorrekturfaktor (TCF) für den Volumenstrom (Referenz 25°C)."""
    return math.exp(2640 * (1/298.15 - 1/(temp_c + 273.15)))

def berechne_tcf_salz(temp_c):
    """
    NEU: Temperaturkorrektur für den Salzdurchgang (Referenz 25°C).
    Warmes Wasser = Höherer Salzdurchgang (schlechterer Rückhalt).
    """
    return math.exp(3020 * (1/298.15 - 1/(temp_c + 273.15)))

def berechne_a_wert(m_test_flow, m_flaeche, m_test_druck, m_test_tds):
    """Berechnet die Permeabilität (A-Wert) basierend auf den realen Datenblatt-Werten."""
    # Osmotischer Druck des spezifischen Test-Wassers (Faustregel: 100 ppm NaCl = ~0.07 bar)
    pi_test = (m_test_tds / 100) * 0.07 
    
    # Netto-Triebdruck beim Test (Druck abzüglich osmotischem Druck)
    ndp_test = max(0.1, m_test_druck - pi_test)
    
    return (m_test_flow / 1000) / (m_flaeche * ndp_test)
