import math
from typing import Tuple

from hydraulik.widerstand import berechne_hydraulischen_widerstand, r_parallel


def _fluss_anteil(r_a: float, r_b: float) -> float:
    """
    Berechnet den Flussanteil von Strang A gegenüber Strang B.

    Bei Parallelschaltung mit gleicher Druckdifferenz gilt Q ~ 1/√R.

    Args:
        r_a: Widerstand Strang A [Pa·s²/m⁶]
        r_b: Widerstand Strang B [Pa·s²/m⁶]

    Returns:
        Flussanteil von Strang A als Dezimalzahl [0..1]
    """
    if r_a <= 0:
        return 0.0
    if r_b <= 0:
        return 1.0
    g_a = 1.0 / math.sqrt(r_a)
    g_b = 1.0 / math.sqrt(r_b)
    return g_a / (g_a + g_b)


def berechne_netzwerk(
    hat_t_stueck: bool,
    d_a: float, l_a: float, sub_a: bool,
    d_a1: float, l_a1: float, d_a2: float, l_a2: float,
    d_b: float, l_b: float, sub_b: bool,
    d_b1: float, l_b1: float, d_b2: float, l_b2: float,
) -> Tuple[float, float, float, float, float]:
    """
    Berechnet den hydraulischen Gesamtwiderstand eines T-Stück-Netzwerks
    sowie die Flussanteile der einzelnen Stränge.

    Netzwerk-Topologie:
        Feed → [Strang A: r_a_main + (r_a1 ∥ r_a2)]
             ↘ [Strang B: r_b_main + (r_b1 ∥ r_b2)]
        Beide Stränge parallel.

    Args:
        hat_t_stueck:       True, wenn ein T-Stück-Netzwerk vorhanden ist
        d_a / l_a:          Durchmesser [mm] / Länge [mm] Haupt-Strang A
        sub_a:              True, wenn Strang A Sub-Verzweigung hat
        d_a1/l_a1/d_a2/l_a2: Sub-Stränge A1 und A2 [mm]
        d_b / l_b:          Durchmesser [mm] / Länge [mm] Haupt-Strang B
        sub_b:              True, wenn Strang B Sub-Verzweigung hat
        d_b1/l_b1/d_b2/l_b2: Sub-Stränge B1 und B2 [mm]

    Returns:
        Tupel (r_netzwerk, pct_a, pct_b, pct_a1, pct_b1):
        - r_netzwerk: Gesamtwiderstand [Pa·s²/m⁶]
        - pct_a / pct_b: Flussanteile Strang A / B [0..1]
        - pct_a1 / pct_b1: Flussanteile Sub-Strang 1 in A / B [0..1]
    """
    if not hat_t_stueck:
        return 0.0, 1.0, 0.0, 0.0, 0.0

    # --- Strang A ---
    r_a1, r_a2 = 0.0, 0.0
    if sub_a:
        r_a1 = berechne_hydraulischen_widerstand(d_a1, l_a1, [], 0)
        r_a2 = berechne_hydraulischen_widerstand(d_a2, l_a2, [], 0)
        r_a_sub = r_parallel(r_a1, r_a2)
    else:
        r_a_sub = 0.0

    r_a_main = berechne_hydraulischen_widerstand(d_a, l_a, [], 0)
    r_a_tot = r_a_main + r_a_sub

    # --- Strang B ---
    r_b1, r_b2 = 0.0, 0.0
    if sub_b:
        r_b1 = berechne_hydraulischen_widerstand(d_b1, l_b1, [], 0)
        r_b2 = berechne_hydraulischen_widerstand(d_b2, l_b2, [], 0)
        r_b_sub = r_parallel(r_b1, r_b2)
    else:
        r_b_sub = 0.0

    r_b_main = berechne_hydraulischen_widerstand(d_b, l_b, [], 0)
    r_b_tot = r_b_main + r_b_sub

    # --- Gesamt-Netzwerk: Strang A ∥ Strang B ---
    r_netzwerk = r_parallel(r_a_tot, r_b_tot)

    pct_a = _fluss_anteil(r_a_tot, r_b_tot)
    pct_b = 1.0 - pct_a

    # Sub-Flussanteile innerhalb der jeweiligen Hauptstränge
    pct_a1 = _fluss_anteil(r_a1, r_a2) if (sub_a and r_a1 > 0 and r_a2 > 0) else 1.0
    pct_b1 = _fluss_anteil(r_b1, r_b2) if (sub_b and r_b1 > 0 and r_b2 > 0) else 1.0

    return r_netzwerk, pct_a, pct_b, pct_a1, pct_b1
