import json
import streamlit as st

def exportiere_konfiguration(inputs_dict):
    """Macht aus dem Python-Dictionary einen formatierten JSON-String."""
    # Wir filtern Streamlit-spezifische Dinge oder leere Keys heraus
    sauberes_dict = {k: v for k, v in inputs_dict.items() if not k.startswith('_')}
    return json.dumps(sauberes_dict, indent=4)

def lade_konfiguration(uploaded_file):
    """Liest die JSON-Datei und schreibt die Werte direkt in den Streamlit Session State."""
    try:
        daten = json.load(uploaded_file)
        
        # Wir durchlaufen alle gespeicherten Werte und legen sie im Session State ab
        for key, value in daten.items():
            st.session_state[key] = value
            
        return True, "Konfiguration erfolgreich geladen!"
    except Exception as e:
        return False, f"Fehler beim Laden: {e}"
