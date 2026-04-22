from fpdf import FPDF

def generiere_pdf(inputs, ergebnisse):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    def add_title(title):
        pdf.set_font("Helvetica", 'B', 14)
        pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    def add_section_header(title):
        pdf.ln(5)
        pdf.set_font("Helvetica", 'B', 12)
        pdf.set_text_color(0, 102, 204) 
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    def add_text(label, value):
        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(95, 7, f"{label}:", border=0)
        pdf.set_font("Helvetica", '', 10)
        pdf.cell(0, 7, str(value), border=0, new_x="LMARGIN", new_y="NEXT")

    # ==========================================
    # SEITE 1: ERGEBNISSE & MODULE
    # ==========================================
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 18)
    pdf.cell(0, 15, "RO-Anlagen Protokoll", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    
    add_title("1. Anlagen-Performance (Gesamtergebnisse)")
    add_text("Gesamt Permeat", f"{ergebnisse['total_permeat']:.1f} l/h")
    add_text("Gesamt Konzentrat", f"{ergebnisse['end_konzentrat_flow']:.1f} l/h")
    add_text("Benoetigter Speisestrom", f"{ergebnisse['q_feed_start_lh']:.1f} l/h")
    ausbeute = (ergebnisse['total_permeat'] / ergebnisse['q_feed_start_lh'] * 100) if ergebnisse['q_feed_start_lh'] > 0 else 0
    add_text("Ist-Ausbeute", f"{ausbeute:.1f} %")
    
    add_section_header("TDS-Qualitaet")
    add_text("Feed TDS (Eingang)", f"{inputs['tds_feed']} ppm")
    add_text("Permeat TDS (Gesamt)", f"{ergebnisse['total_permeat_tds']:.1f} ppm")
    add_text("Konzentrat TDS (Abfluss)", f"{ergebnisse['final_konzentrat_tds']:.0f} ppm")
    
    add_section_header("Hydraulik & Drossel")
    add_text("Effektiver Druck an Anlage", f"{ergebnisse['p_effektiv_start']:.2f} bar")
    add_text("Restdruck vor Ventil", f"{ergebnisse['konzentrat_druck_verlauf']:.2f} bar")
    add_text("Abzubauender Druck (Delta P)", f"{ergebnisse['abzubauender_druck']:.2f} bar")
    add_text("Empfohlener Drossel-Durchmesser", f"{ergebnisse['empfohlene_drossel_mm']:.2f} mm")

    add_section_header("Detaillierte Modul-Ergebnisse")
    for mod in ergebnisse['membran_daten']:
        pdf.set_font("Helvetica", 'I', 11)
        pdf.cell(0, 7, f"> {mod['Membran']}", new_x="LMARGIN", new_y="NEXT")
        add_text("   Eingangsdruck", f"{mod['Eingangsdruck (bar)']} bar")
        
        # NEU: Flux im PDF ausgeben
        if 'Flux (LMH)' in mod:
            add_text("   Flux", f"{mod['Flux (LMH)']} LMH")
            
        if 'Gegendruck (bar)' in mod:
            add_text("   Gegendruck Permeat", f"{mod['Gegendruck (bar)']} bar")
        add_text("   Permeat", f"{mod['Permeat (l/h)']} l/h")
        add_text("   Konzentrat", f"{mod['Konzentrat (l/h)']} l/h")
        add_text("   Permeat TDS", f"{mod['Permeat TDS (ppm)']} ppm")
        add_text("   Konzentrat TDS", f"{mod['Konz. TDS (ppm)']} ppm")
        pdf.ln(3)

    # ==========================================
    # SEITE 2: VERSCHALTUNG & AUFBAU
    # ==========================================
    pdf.add_page()
    add_title("2. Parametrisierung: Anlage & Membrane")
    add_text("Gewaehlte Schaltung", inputs['schaltung'])
    add_text("Anzahl Membranen", inputs['anzahl_membranen'])
    add_text("Ziel-Ausbeute Anlage", f"{inputs['ausbeute_pct']} %")

    add_section_header("Membrane & System")
    add_text("Filterflaeche", f"{inputs['m_flaeche']} m2")
    add_text("Nennleistung Test", f"{inputs['m_test_flow']} l/h")
    add_text("Test-Druck", f"{inputs['m_test_druck']} bar")
    add_text("Rueckhalt", f"{inputs['m_rueckhalt'] * 100:.1f} %")
    add_text("Systemdruck (nach Pumpe)", f"{inputs['p_system']} bar")
    add_text("Wassertemperatur", f"{inputs['temp']} Grad C")

    # ==========================================
    # SEITE 3: ROHRLEITUNGEN KOMPLETT
    # ==========================================
    pdf.add_page()
    add_title("3. Rohrleitungen & Hydraulik (Alle Eingaben)")
    
    add_section_header("Zuleitung (Saugseite / Druckseite)")
    add_text("Saugseite Innen-Ø", f"{inputs['zuleitung_saug']['d']} mm")
    add_text("Saugseite Laenge", f"{inputs['zuleitung_saug']['l']} mm")
    add_text("Saugseite Boegen (90 Grad)", f"{inputs['zuleitung_saug']['b']}")
    add_text("Druckseite Hauptleitung Ø", f"{inputs['zuleitung_druck']['d']} mm")
    add_text("Druckseite Hauptleitung Laenge", f"{inputs['zuleitung_druck']['l']} mm")
    
    add_section_header("Konzentratleitungen")
    if inputs.get('konz_leitungen'):
        for i, l in enumerate(inputs['konz_leitungen']):
            add_text(f"  Zweig {i+1} (Ø | Laenge | Boegen)", f"{l['d']} mm | {l['l']} mm | {l['b']}")
    if inputs.get('konz_out'):
        cout = inputs['konz_out']
        add_text("  Auslass/Sammelleitung Konzentrat", f"{cout['d']} mm | {cout['l']} mm | {cout['b']} Boegen")

    add_section_header("Permeatleitungen")
    if inputs.get('perm_leitungen'):
        for i, l in enumerate(inputs['perm_leitungen']):
            add_text(f"  Zweig {i+1} (Ø | Laenge | Boegen)", f"{l['d']} mm | {l['l']} mm | {l['b']}")
    if inputs.get('perm_out'):
        pout = inputs['perm_out']
        add_text("  Sammelrohr Permeat (Ø | Laenge | Boegen)", f"{pout['d']} mm | {pout['l']} mm | {pout['b']}")
    if inputs.get('perm_schlauch'):
        ps = inputs['perm_schlauch']
        add_text("  Auslassschlauch (Ø | Laenge | Hoehe)", f"{ps['d']} mm | {ps['l']} mm | {ps['h']} m Hoehendifferenz")

    return bytes(pdf.output())
