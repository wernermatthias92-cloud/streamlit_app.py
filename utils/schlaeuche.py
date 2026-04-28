SCHLAUCH_DATENBANK = {
    "Manuelle Eingabe": {
        "d_innen": 13.2, 
        "d_aussen": 19.0, 
        "info": "Eigene Innendurchmesser manuell eintragen"
    },
    
    # --- PU- / PNEUMATIKSCHLÄUCHE (Meist definiert über Außen-Ø) ---
    "PU Schlauch 4 mm (4x2)": {
        "d_innen": 2.0, "d_aussen": 4.0, "info": "Sehr dünner PU-Schlauch (Außen 4 mm / Innen 2 mm)"
    },
    "PU Schlauch 6 mm (6x4)": {
        "d_innen": 4.0, "d_aussen": 6.0, "info": "Standard PU-Schlauch (Außen 6 mm / Innen 4 mm)"
    },
    "PU Schlauch 8 mm (8x5)": {
        "d_innen": 5.0, "d_aussen": 8.0, "info": "PU-Schlauch dickwandig (Außen 8 mm / Innen 5 mm)"
    },
    "PU Schlauch 8 mm (8x6)": {
        "d_innen": 6.0, "d_aussen": 8.0, "info": "PU-Schlauch dünnwandig (Außen 8 mm / Innen 6 mm)"
    },
    "PU Schlauch 10 mm (10x7)": {
        "d_innen": 7.0, "d_aussen": 10.0, "info": "PU-Schlauch dickwandig (Außen 10 mm / Innen 7 mm)"
    },
    "PU Schlauch 10 mm (10x8)": {
        "d_innen": 8.0, "d_aussen": 10.0, "info": "PU-Schlauch dünnwandig (Außen 10 mm / Innen 8 mm)"
    },
    "PU Schlauch 12 mm (12x8)": {
        "d_innen": 8.0, "d_aussen": 12.0, "info": "PU-Schlauch dickwandig (Außen 12 mm / Innen 8 mm)"
    },
    "PU Schlauch 12 mm (12x9)": {
        "d_innen": 9.0, "d_aussen": 12.0, "info": "PU-Schlauch dünnwandig (Außen 12 mm / Innen 9 mm)"
    },

    # --- GEWEBESCHLÄUCHE / PVC (Meist definiert über Zoll-Innen-Ø) ---
    "Gewebeschlauch 1/4\" (6x12)": {
        "d_innen": 6.0, "d_aussen": 12.0, "info": "Standard PVC-Schlauch 1/4 Zoll (Innen 6 mm)"
    },
    "Gewebeschlauch 3/8\" (9x15)": {
        "d_innen": 9.0, "d_aussen": 15.0, "info": "Standard PVC-Schlauch 3/8 Zoll (Innen 9 mm)"
    },
    "Gewebeschlauch 1/2\" (13x19)": {
        "d_innen": 13.0, "d_aussen": 19.0, "info": "Klassischer Gartenschlauch 1/2 Zoll (Innen 13 mm)"
    },
    "Gewebeschlauch 5/8\" (16x22)": {
        "d_innen": 16.0, "d_aussen": 22.0, "info": "Großer Gartenschlauch 5/8 Zoll (Innen 16 mm)"
    },
    "Gewebeschlauch 3/4\" (19x26)": {
        "d_innen": 19.0, "d_aussen": 26.0, "info": "Profi-Schlauch 3/4 Zoll (Innen 19 mm)"
    },
    "Gewebeschlauch 1\" (25x33)": {
        "d_innen": 25.0, "d_aussen": 33.0, "info": "Industrie-Schlauch 1 Zoll (Innen 25 mm)"
    },
    "Gewebeschlauch 1 1/4\" (32x42)": {
        "d_innen": 32.0, "d_aussen": 42.0, "info": "Industrie-Schlauch 1 1/4 Zoll (Innen 32 mm)"
    },
    "Gewebeschlauch 1 1/2\" (38x48)": {
        "d_innen": 38.0, "d_aussen": 48.0, "info": "Industrie-Schlauch 1 1/2 Zoll (Innen 38 mm)"
    }
}

def get_schlauch_namen():
    """Gibt eine Liste aller verfügbaren Schlauchnamen für Dropdown-Menüs zurück."""
    return list(SCHLAUCH_DATENBANK.keys())

def get_schlauch_innen_d(schlauch_name):
    """Gibt den physikalisch relevanten Innendurchmesser zurück."""
    if schlauch_name in SCHLAUCH_DATENBANK:
        return SCHLAUCH_DATENBANK[schlauch_name]["d_innen"]
    return 13.2 # Fallback
