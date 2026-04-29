PUMPEN_DATENBANK = {
    # --- KREISELPUMPEN (Klassische Kennlinie) ---
    "Manuelle Eingabe": {
        "typ": "Kreisel",
        "p_max": 11.5, 
        "q_max": 1920.0, 
        "exponent": 2.0,
        "info": "Eigene Werte definieren (Exponent 2 = einstufig, 3 = mehrstufig)"
    },
    "Ebara Matrix 3-5T (230V)": {
        "typ": "Kreisel",
        "p_max": 5.6, 
        "q_max": 4800.0, 
        "exponent": 3.0,
        "info": "Robuste mehrstufige Kreiselpumpe, extrem flache Druck-Kennlinie"
    },
    "Speck MTX 3-60 (230V)": {
        "typ": "Kreisel",
        "p_max": 6.8, 
        "q_max": 4800.0, 
        "exponent": 3.0,
        "info": "Mehrstufige Hochdruck-Kreiselpumpe"
    },
    "WILO MHIL 107-E-1-230-50-2/EC /B": {
        "typ": "Kreisel",
        "p_max": 6.6, 
        "q_max": 3000.0, 
        "exponent": 3.0,
        "info": "7-stufige horizontale Hochdruck-Kreiselpumpe (0.55 kW)"
    },
    
    # --- VERDRÄNGERPUMPEN (Membran / Rotation für 12V etc.) ---
    "Shurflo 8000 Serie (12V)": {
        "typ": "Verdraenger",
        "p_max": 6.9,   
        "q_max": 340.0, 
        "exponent": 1.0, 
        "info": "Kompakte 12V Membranpumpe, ideal für Rucksäcke (ca. 1.5 GPM)"
    },
    "Seaflo 55 Serie (12V)": {
        "typ": "Verdraenger",
        "p_max": 4.1, 
        "q_max": 1130.0,
        "exponent": 1.0,
        "info": "Leistungsstarke 12V Membranpumpe für Trolleys (ca. 5.5 GPM)"
    },
    "Fluid-o-Tech PO 4060 (1450 rpm)": {
        "typ": "Verdraenger",
        "p_max": 18.0,   
        "q_max": 1600.0, 
        "exponent": 1.0, 
        "info": "Industrie-Drehschieberpumpe an IEC 80 Motor, pulsationsarm."
    },
    "DSP800": {
        "typ": "Verdraenger",
        "p_max": 18.0,   
        "q_max": 1000.0, 
        "exponent": 1.0, 
        "info": "Industrie-Drehschieberpumpe (800 l/h)"
    },
    "DSP600": {
        "typ": "Verdraenger",
        "p_max": 18.0,   
        "q_max": 600.0, 
        "exponent": 1.0, 
        "info": "Industrie-Drehschieberpumpe (600 l/h)"
    }
}

def get_pumpen_namen():
    return list(PUMPEN_DATENBANK.keys())

def get_pumpen_typ(name):
    if name in PUMPEN_DATENBANK:
        return PUMPEN_DATENBANK[name].get("typ", "Kreisel")
    return "Kreisel"
