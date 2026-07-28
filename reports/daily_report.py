import pandas as pd
import os
from datetime import date as dt_date

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "files")

def _ensure_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# Excel Report
# ─────────────────────────────────────────────

def generate_excel_report(attendance_data, filter_date=None, section=None, start_date=None, end_date=None):
    """
    Generate a styled Excel report from attendance data.
    """
    _ensure_dir()

    if start_date and end_date:
        label = f"{start_date}_to_{end_date}"
    else:
        label = f"{filter_date or dt_date.today()}"
        
    if section:
        label += f"_{section}"

    filename = f"Attendance_{label}.xlsx"
    filepath = os.path.join(REPORTS_DIR, filename)

    columns = ['Date', 'Name', 'Roll Number', 'Section', 'Email', 'Phone', 'Period', 'Time Marked', 'Status']

    if attendance_data:
        rows = []
        for rec in attendance_data:
            # rec = (name, roll, section, period, time, status, date, email, phone)
            rows.append({
                'Date':        str(rec[6]) if rec[6] else '',
                'Name':        rec[0],
                'Roll Number': rec[1],
                'Section':     rec[2],
                'Email':       rec[7] if len(rec) > 7 else '',
                'Phone':       rec[8] if len(rec) > 8 else '',
                'Period':      f"Period {rec[3]}",
                'Time Marked': str(rec[4]) if rec[4] else '',
                'Status':      rec[5] or 'Present',
            })
        df = pd.DataFrame(rows, columns=columns)
    else:
        df = pd.DataFrame(columns=columns)

    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Attendance')
        ws = writer.sheets['Attendance']

        # Auto-width columns
        for col in ws.columns:
            max_len = max((len(str(cell.value)) for cell in col if cell.value), default=10)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    return filepath


# ─────────────────────────────────────────────
# PDF Report (using built-in reportlab or fpdf2)
# ─────────────────────────────────────────────

def generate_pdf_report(summary_data, filter_date=None, section=None):
    """
    Generate a PDF attendance summary report.
    summary_data: list from get_attendance_summary()
    Each row: (id, name, roll, section, phone, periods_present, total_periods, is_present, pct)
    Returns filepath.
    """
    _ensure_dir()

    if not filter_date:
        filter_date = dt_date.today()

    label = f"{filter_date}"
    if section:
        label += f"_{section}"

    filename = f"AttendanceSummary_{label}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        doc = SimpleDocTemplate(filepath, pagesize=A4,
                                leftMargin=15*mm, rightMargin=15*mm,
                                topMargin=15*mm, bottomMargin=15*mm)
        styles  = getSampleStyleSheet()
        content = []

        # Title
        title_style = ParagraphStyle('Title', fontSize=18, spaceAfter=4, alignment=TA_CENTER,
                                     fontName='Helvetica-Bold', textColor=colors.HexColor('#1a73e8'))
        sub_style   = ParagraphStyle('Sub', fontSize=10, spaceAfter=12, alignment=TA_CENTER,
                                     textColor=colors.HexColor('#666666'))

        content.append(Paragraph("Smart Attendance System", title_style))
        date_str = filter_date.strftime("%d %B %Y") if hasattr(filter_date, 'strftime') else str(filter_date)
        sec_str  = f" | Section: {section}" if section else " | All Sections"
        content.append(Paragraph(f"Attendance Report — {date_str}{sec_str}", sub_style))
        content.append(Spacer(1, 6*mm))

        # Stats row
        total   = len(summary_data)
        present = sum(1 for r in summary_data if r[7] == 1)
        absent  = total - present
        pct     = round((present / total) * 100, 1) if total else 0

        stats_data = [
            ['Total Students', 'Present', 'Absent', 'Attendance Rate'],
            [str(total), str(present), str(absent), f"{pct}%"],
        ]
        stats_table = Table(stats_data, colWidths=[45*mm, 40*mm, 40*mm, 45*mm])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 10),
            ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f0f4ff')),
            ('FONTNAME',   (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 1), (-1, 1), 13),
            ('ROWBACKGROUNDS', (0, 1), (-1, 1), [colors.HexColor('#f0f4ff')]),
            ('BOX',        (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('TOPPADDING',    (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        content.append(stats_table)
        content.append(Spacer(1, 6*mm))

        # Student table
        headers = ['#', 'Name', 'Roll No.', 'Section', 'Status', 'Periods', 'Att. %']
        table_data = [headers]

        for i, r in enumerate(summary_data, 1):
            status = 'Present' if r[7] == 1 else 'Absent'
            table_data.append([
                str(i), r[1], r[2], r[3], status,
                f"{r[5]}/{r[6]}", f"{r[8]}%"
            ])

        col_widths = [10*mm, 55*mm, 28*mm, 22*mm, 24*mm, 22*mm, 18*mm]
        student_table = Table(table_data, colWidths=col_widths, repeatRows=1)

        row_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, -1), 8),
            ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN',      (1, 1), (1, -1), 'LEFT'),
            ('GRID',       (0, 0), (-1, -1), 0.4, colors.HexColor('#cccccc')),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9ff')]),
        ]

        # Color Present/Absent rows
        for i, r in enumerate(summary_data, 1):
            if r[7] == 1:
                row_styles.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#1a8f5a')))
                row_styles.append(('FONTNAME',  (4, i), (4, i), 'Helvetica-Bold'))
            else:
                row_styles.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor('#cc3333')))
                row_styles.append(('FONTNAME',  (4, i), (4, i), 'Helvetica-Bold'))

        student_table.setStyle(TableStyle(row_styles))
        content.append(student_table)

        # Footer
        content.append(Spacer(1, 8*mm))
        footer_style = ParagraphStyle('Footer', fontSize=8, alignment=TA_CENTER,
                                      textColor=colors.HexColor('#999999'))
        content.append(Paragraph(f"Generated by Smart Attendance System • {dt_date.today().strftime('%d %B %Y')}", footer_style))

        doc.build(content)
        return filepath

    except ImportError:
        # Fallback: plain text PDF using fpdf2
        return _generate_simple_pdf(summary_data, filter_date, section, filepath)


def _generate_simple_pdf(summary_data, filter_date, section, filepath):
    """Fallback PDF using fpdf2 if reportlab is not installed."""
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 16)
        pdf.cell(0, 10, 'Smart Attendance System', ln=True, align='C')
        pdf.set_font('Helvetica', '', 11)
        date_str = str(filter_date)
        sec_str  = f" | Section: {section}" if section else ""
        pdf.cell(0, 8, f"Attendance Report - {date_str}{sec_str}", ln=True, align='C')
        pdf.ln(5)

        total   = len(summary_data)
        present = sum(1 for r in summary_data if r[7] == 1)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, f"Total: {total}  |  Present: {present}  |  Absent: {total - present}", ln=True, align='C')
        pdf.ln(4)

        # Table header
        pdf.set_fill_color(26, 115, 232)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('Helvetica', 'B', 9)
        headers = ['#', 'Name', 'Roll', 'Section', 'Status', '%']
        widths  = [10, 65, 30, 25, 30, 20]
        for h, w in zip(headers, widths):
            pdf.cell(w, 8, h, border=1, fill=True)
        pdf.ln()

        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Helvetica', '', 9)
        for i, r in enumerate(summary_data, 1):
            fill = i % 2 == 0
            if fill:
                pdf.set_fill_color(240, 244, 255)
            status = 'Present' if r[7] == 1 else 'Absent'
            row = [str(i), r[1], r[2], r[3], status, f"{r[8]}%"]
            for val, w in zip(row, widths):
                pdf.cell(w, 7, str(val)[:20], border=1, fill=fill)
            pdf.ln()

        pdf.output(filepath)
        return filepath
    except ImportError:
        raise RuntimeError("Neither reportlab nor fpdf2 is installed. Run: pip install reportlab")
