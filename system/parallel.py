import math
from typing import List

# --- Physikalische Konstanten ---
DICHTE_WASSER_KG_M3 = 1000.0   # kg/m³
LAMBDA_ROHR = 0.03               # Rohrreibungszahl (glatte Rohre, Näherung)
ZETA_90_GRAD_BOGEN = 1.2         # Verlustbeiwert für 90°-Rohrbogen
ZETA_DROSSEL_FAKTOR = 1.5        # Verlustbeiwert-Faktor für Blendendrosseln
RHO_HALB = DICHTE_WASSER_KG_M3 / 2  # = 500, wird in R-Formel benötigt


def berechne_hydraulischen_widerstand(
    d_inner_mm: float,
    laenge_mm: float,
    drosseln_liste: List[float],
    anzahl_90_grad: int,
) -> float:
    """
    Berechnet den hydraulischen Widerstand R [Pa·s²/m⁶] einer Rohrleitung.

    Druckverlust-Modell: ΔP [Pa] = R · Q² [m³/s]

    Args:
        d_inner_mm:      Innendurchmesser [mm]
        laenge_mm:       Rohrlänge [mm]
        drosseln_liste:  Liste der Drosseldurchmesser [mm]; leere Liste = keine Drossel
        anzahl_90_grad:  Anzahl der 90°-Rohrbögen

    Returns:
        Hydraulischer Widerstand R [Pa·s²/m⁶]; 1e12 bei ungültigem Durchmesser
    """
    if d_inner_mm <= 0:
        return 1e12

    d_m = d_inner_mm / 1000.0
    area = math.pi * (d_m / 2) ** 2

    zeta_rohr = LAMBDA_ROHR * (laenge_mm / 1000.0) / d_m
    zeta_drossel = sum(
        ZETA_DROSSEL_FAKTOR * (d_inner_mm / d) ** 4
        for d in drosseln_liste if d > 0
    )
    zeta_bogen = anzahl_90_grad * ZETA_90_GRAD_BOGEN
    zeta_total = zeta_rohr + zeta_drossel + zeta_bogen

    return zeta_total * RHO_HALB / (area ** 2)


def r_parallel(r1: float, r2: float) -> float:
    """
    Gesamtwiderstand zweier hydraulischer Widerstände in Parallelschaltung.

    Herleitung: Bei gleicher Druckdifferenz gilt Q ~ 1/√R, daher:
        1/√R_ges = 1/√R1 + 1/√R2

    Args:
        r1: Widerstand Strang 1 [Pa·s²/m⁶]
        r2: Widerstand Strang 2 [Pa·s²/m⁶]

    Returns:
        Paralleler Gesamtwiderstand [Pa·s²/m⁶]
    """
    if r1 <= 0:
        return r2
    if r2 <= 0:
        return r1
    return (1.0 / math.sqrt(r1) + 1.0 / math.sqrt(r2)) ** -2


def empfehle_drossel_durchmesser(flow_lh: float, delta_p_bar: float) -> float:
    """
    Empfiehlt einen Drosseldurchmesser [mm] für gegebenen Durchfluss und Druckabfall.

    Basiert auf der Blenden-Gleichung mit Durchflusskoeffizient Cd = 0,6.

    Args:
        flow_lh:     Volumenstrom [l/h]
        delta_p_bar: Gewünschter Druckabfall [bar]

    Returns:
        Empfohlener Drosseldurchmesser [mm]; 0 bei ungültigen Eingaben
    """
    if flow_lh <= 0 or delta_p_bar <= 0:
        return 0.0

    q_ms = (flow_lh / 1000.0) / 3600.0
    delta_p_pa = delta_p_bar * 1e5
    # Spaltgeschwindigkeit aus Energiegleichung (vereinfacht, Cd implizit in 2.5)
    v_spalt = math.sqrt((2.0 * delta_p_pa) / (2.5 * DICHTE_WASSER_KG_M3))
    area_m2 = q_ms / v_spalt
    d_m = math.sqrt((4.0 * area_m2) / math.pi)
    return d_m * 1000.0
