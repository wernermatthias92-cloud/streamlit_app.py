import math

# --- Konstanten ---
TCF_AKTIVIERUNGSENERGIE_K = 2640  # Aktivierungsenergie für RO-Membranen [K]
T_REF_K = 298.15                  # Referenztemperatur 25 °C in Kelvin
TDS_TEST_PPM = 1500.0             # Standard-Testkonzentration NaCl [ppm]
OSMOTISCHER_DRUCKKOEFF = 0.07     # Osmotischer Druckkoeffizient [bar / (ppm/100)]


def berechne_tcf(temp_c: float) -> float:
    """
    Berechnet den Temperaturkorrekturfaktor (TCF) bezogen auf 25 °C.

    Höherer TCF bedeutet bessere Permeabilität bei wärmeren Temperaturen.

    Args:
        temp_c: Betriebstemperatur [°C]

    Returns:
        Dimensionsloser Temperaturkorrekturfaktor [-]
    """
    return math.exp(TCF_AKTIVIERUNGSENERGIE_K * (1.0 / T_REF_K - 1.0 / (temp_c + 273.15)))


def berechne_a_wert(m_test_flow: float, m_flaeche: float, m_test_druck: float) -> float:
    """
    Berechnet die Wasserpermeabilität (A-Wert) der Membran aus Testdaten.

    Formel: A = Q_p / (A_m · NDP)
    Mit NDP = p_test - π_test (osmotischer Gegendruck bei 1500 ppm NaCl ≈ 1,05 bar)

    Args:
        m_test_flow:  Permeatfluss unter Testbedingungen [l/h]
        m_flaeche:    Aktive Membranfläche [m²]
        m_test_druck: Testdruck [bar]

    Returns:
        A-Wert [m³/(m²·s·bar)] (Wasserpermeabilitätskoeffizient)
    """
    pi_test = (TDS_TEST_PPM / 100.0) * OSMOTISCHER_DRUCKKOEFF
    return (m_test_flow / 1000.0) / (m_flaeche * (m_test_druck - pi_test))
