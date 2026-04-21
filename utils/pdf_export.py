from fpdf import FPDF

def generiere_pdf(inputs, ergebnisse):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Hilfsfunktionen für einheitliches Design
    def add_title(title):
        pdf.set_font("Helvetica", 'B', 16)
        pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)

    def add_text(label, value):
        pdf.set_font("Helvetica", 'B', 11)
        pdf.cell(60, 8, f"{label}:", border=0)
        pdf.set_font("Helvetica", '', 11)
        pdf.cell(0, 8, str(value), border=0, new_x="LMARGIN", new_y="NEXT")

    # ==========================================
    # SEITE 1: ERGEBNISSE
    # ==========================================
    pdf.add_page()
    add_title("Anlagen-Performance (Ergebnisse)")
    
    add_text("Gesamt Permeat", f"{ergebnisse['total_permeat']:.1f} l/h")
    add_text("Gesamt Konzentrat", f"{ergebnisse['end_konzentrat_flow']:.1f} l/h")
    add_text("Benoetigter Speisestrom", f"{ergebnisse['q_feed_start_lh']:.1f} l/h")
    
    pdf.ln(5)
    add_text("Feed TDS (Eingang)", f"{inputs['tds_feed']} ppm")
    add_text("Permeat TDS (Gesamt)", f"{ergebnisse['total_permeat_tds']:.1f} ppm")
    add_text("Konzentrat TDS (Abfluss)", f"{ergebnisse['final_konzentrat_tds']:.0f} ppm")
    
    pdf.ln(10)
    add_title("Hydraulik & Drossel")
    add_text("Effektiver Druck an Anlage", f"{ergebnisse['p_effektiv_start']:.2f} bar")
    add_text("Restdruck vor Ventil", f"{ergebnisse['konzentrat_druck_verlauf']:.2f} bar")
    add_text("Abzubauender Druck (Delta P)", f"{ergebnisse['abzubauender_druck']:.2f} bar")
    add_text("Empfohlener Drossel-Durchmesser", f"{ergebnisse['empfohlene_drossel_mm']:.2f} mm")

    # ==========================================
    # SEITE 2: VERSCHALTUNG & AUFBAU
    # ==========================================
    pdf.add_page()
    add_title("1. Verschaltung & Aufbau")
    add_text("Gewaehlte Schaltung", inputs['schaltung'])
    add_text("Anzahl Membranen", inputs['anzahl_membranen'])
    add_text("Ziel-Ausbeute Anlage", f"{inputs['ausbeute_pct']} %")

    # ==========================================
    # SEITE 3: MEMBRANE & SYSTEM
    # ==========================================
    pdf.add_page()
    add_title("2. Membrane & System")
    add_text("Filterflaeche", f"{inputs['m_flaeche']} m2")
    add_text("Nennleistung Test", f"{inputs['m_test_flow']} l/h")
    add_text("Test-Druck", f"{inputs['m_test_druck']} bar")
    add_text("Rueckhalt", f"{inputs['m_rueckhalt'] * 100:.1f} %")
    pdf.ln(5)
    add_text("Feed TDS Parameter", f"{inputs['tds_feed']} ppm")
    add_text("Wassertemperatur", f"{inputs['temp']} Grad C")
    add_text("Systemdruck (nach Pumpe)", f"{inputs['p_system']} bar")

    # ==========================================
    # SEITE 4: ROHRLEITUNGEN (Zusammenfassung)
    # ==========================================
    pdf.add_page()
    add_title("3. Rohrleitungen (Auszug)")
    add_text("Druckverlust Saugseite", f"{ergebnisse['p_verlust_saug']:.3f} bar")
    add_text("Verlust Hauptleitung (Druckseite)", f"{ergebnisse['p_verlust_druck_haupt']:.3f} bar")
    add_text("Verlust T-Stueck Netzwerk", f"{ergebnisse['p_verlust_netzwerk']:.3f} bar")

    # PDF als Byte-String zurückgeben, damit Streamlit es als Download anbieten kann
    return bytes(pdf.output())
