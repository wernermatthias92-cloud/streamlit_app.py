PUMPEN_DATENBANK = {
    "Manuelle Eingabe": {
        "p_max": 11.5, 
        "q_max": 1920.0, 
        "exponent": 2.0,
        "info": "Eigene Werte definieren (Exponent 2 = einstufig, 3 = mehrstufig)"
    },
    "Ebara Matrix 3-5T (230V)": {
        "p_max": 5.6, 
        "q_max": 4800.0, 
        "exponent": 3.0,
        "info": "Robuste mehrstufige Kreiselpumpe, extrem flache Druck-Kennlinie"
    },
    "Speck MTX 3-60 (230V)": {
        "p_max": 6.0, 
        "q_max": 4500.0, 
        "exponent": 3.0,
        "info": "Mehrstufige Hochdruck-Kreiselpumpe"
    },
    "WILO MHIL 107-E-1-230-50-2/EC /B": {
        "p_max": 6.6, 
        "q_max": 3000.0, 
        "exponent": 3.0,
        "info": "7-stufige horizontale Hochdruck-Kreiselpumpe (0.55 kW)"
    }
}

def get_pumpen_namen():
    return list(PUMPEN_DATENBANK.keys())
