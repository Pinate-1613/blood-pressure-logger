import os
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Circle, PolyLine, Group

class BPPdfGenerator:
    @staticmethod
    def get_bp_category(sys, dia):
        if sys < 120 and dia < 80:
            return "Normal", colors.HexColor("#059669")
        elif 120 <= sys < 130 and dia < 80:
            return "Elevated", colors.HexColor("#D97706")
        elif (130 <= sys < 140) or (80 <= dia < 90):
            return "High (Stage 1)", colors.HexColor("#EA580C")
        elif (140 <= sys < 180) or (90 <= dia < 120):
            return "High (Stage 2)", colors.HexColor("#DC2626")
        else:
            return "Crisis", colors.HexColor("#991B1B")

    @staticmethod
    def draw_vector_chart(records, width=460, height=160):
        """
        Draws a sharp vector line chart directly in ReportLab for the PDF report.
        """
        d = Drawing(width, height)
        
        # Background box
        d.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=1))
        
        if not records:
            d.add(String(width/2, height/2, "No chart data available", textAnchor="middle", fontSize=12, fillColor=colors.HexColor("#94A3B8")))
            return d

        # Sort chronologically
        sorted_records = sorted(records, key=lambda x: x['timestamp'])
        n = len(sorted_records)

        # Plot parameters
        pad_l, pad_r, pad_t, pad_b = 40, 15, 20, 25
        plot_w = width - pad_l - pad_r
        plot_h = height - pad_t - pad_b

        # Scales
        all_sys = [r['systolic'] for r in sorted_records]
        all_dia = [r['diastolic'] for r in sorted_records]
        
        max_val = max(max(all_sys), 150)
        min_val = min(min(all_dia), 60)
        
        # Round margins
        max_val = ((max_val // 20) + 1) * 20
        min_val = max(0, ((min_val // 20) - 1) * 20)
        
        val_range = max_val - min_val
        if val_range <= 0:
            val_range = 100

        # Draw Grid Lines & Y-Axis Labels
        y_step = 20
        curr_y = min_val
        while curr_y <= max_val:
            y_ratio = (curr_y - min_val) / val_range
            cy = pad_b + (y_ratio * plot_h)
            
            # Grid line
            d.add(Line(pad_l, cy, pad_l + plot_w, cy, strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=0.5))
            # Label
            d.add(String(pad_l - 8, cy - 3, str(int(curr_y)), textAnchor="end", fontSize=8, fillColor=colors.HexColor("#64748B")))
            
            curr_y += y_step

        # Plot points
        sys_coords = []
        dia_coords = []
        
        for i, r in enumerate(sorted_records):
            x_ratio = i / (n - 1) if n > 1 else 0.5
            cx = pad_l + (x_ratio * plot_w)
            
            # Sys
            sys_ratio = (r['systolic'] - min_val) / val_range
            cy_sys = pad_b + (sys_ratio * plot_h)
            sys_coords.append((cx, cy_sys))
            
            # Dia
            dia_ratio = (r['diastolic'] - min_val) / val_range
            cy_dia = pad_b + (dia_ratio * plot_h)
            dia_coords.append((cx, cy_dia))
            
            # Bottom X Date labels (draw max 6 labels)
            if n <= 6 or i % (n // 5 or 1) == 0 or i == n - 1:
                try:
                    dt = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
                    lbl = dt.strftime("%m-%d")
                except ValueError:
                    lbl = r['timestamp'][:10]
                d.add(String(cx, pad_b - 12, lbl, textAnchor="middle", fontSize=7, fillColor=colors.HexColor("#64748B")))

        # Connect lines
        sys_flat = []
        for x, y in sys_coords: sys_flat.extend([x, y])
        dia_flat = []
        for x, y in dia_coords: dia_flat.extend([x, y])

        # Draw Systolic Line (Coral Red)
        if len(sys_flat) >= 4:
            d.add(PolyLine(sys_flat, strokeColor=colors.HexColor("#EF4444"), strokeWidth=2))
        # Draw Diastolic Line (Teal Blue)
        if len(dia_flat) >= 4:
            d.add(PolyLine(dia_flat, strokeColor=colors.HexColor("#06B6D4"), strokeWidth=2))

        # Add visual point circles
        for i in range(n):
            # Sys dot
            d.add(Circle(sys_coords[i][0], sys_coords[i][1], 3, fillColor=colors.HexColor("#EF4444"), strokeColor=colors.white, strokeWidth=1))
            # Dia dot
            d.add(Circle(dia_coords[i][0], dia_coords[i][1], 3, fillColor=colors.HexColor("#06B6D4"), strokeColor=colors.white, strokeWidth=1))

        # Add Legend
        # Sys
        d.add(Circle(pad_l + 10, height - 10, 4, fillColor=colors.HexColor("#EF4444"), strokeColor=colors.white, strokeWidth=0.5))
        d.add(String(pad_l + 20, height - 13, "Systolic (mmHg)", fontSize=8, fillColor=colors.HexColor("#334155")))
        # Dia
        d.add(Circle(pad_l + 120, height - 10, 4, fillColor=colors.HexColor("#06B6D4"), strokeColor=colors.white, strokeWidth=0.5))
        d.add(String(pad_l + 130, height - 13, "Diastolic (mmHg)", fontSize=8, fillColor=colors.HexColor("#334155")))

        return d

    @classmethod
    def generate_report(cls, records, filepath, user_name="User", date_range="All Time", stats=None):
        """
        Creates a PDF report at the target filepath.
        """
        # Ensure parent directories exist
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        # Modify / Add styles
        title_style = ParagraphStyle(
            'ReportTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1E3A8A"), # Navy
            spaceAfter=6
        )
        
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569"),
            spaceAfter=15
        )

        h2_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=12,
            spaceAfter=8
        )

        cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#334155")
        )
        
        cell_bold_style = ParagraphStyle(
            'TableCellBold',
            parent=cell_style,
            fontName='Helvetica-Bold'
        )

        story = []

        # 1. Header Banner Block
        story.append(Paragraph("BLOOD PRESSURE HEALTH REPORT", title_style))
        gen_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        story.append(Paragraph(f"<b>Patient:</b> {user_name} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Report Period:</b> {date_range} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Generated:</b> {gen_time}", subtitle_style))
        story.append(Spacer(1, 5))

        # 2. Key Statistics Block
        story.append(Paragraph("Health Overview & Statistics", h2_style))
        
        if stats:
            avg_sys = f"{stats.get('avg_sys', 0):.1f}" if stats.get('avg_sys') else "N/A"
            avg_dia = f"{stats.get('avg_dia', 0):.1f}" if stats.get('avg_dia') else "N/A"
            avg_pulse = f"{stats.get('avg_pulse', 0):.1f}" if stats.get('avg_pulse') else "N/A"
            min_sys = stats.get('min_sys', 'N/A')
            max_sys = stats.get('max_sys', 'N/A')
            min_dia = stats.get('min_dia', 'N/A')
            max_dia = stats.get('max_dia', 'N/A')
            count = stats.get('count', 0)
        else:
            avg_sys, avg_dia, avg_pulse = "N/A", "N/A", "N/A"
            min_sys, max_sys, min_dia, max_dia = "N/A", "N/A", "N/A", "N/A"
            count = len(records)

        # Style a grid table for stats
        stats_data = [
            [
                Paragraph("<b>Total Readings:</b>", cell_style), Paragraph(str(count), cell_bold_style),
                Paragraph("<b>Average Systolic:</b>", cell_style), Paragraph(f"{avg_sys} mmHg", cell_bold_style),
                Paragraph("<b>Average Diastolic:</b>", cell_style), Paragraph(f"{avg_dia} mmHg", cell_bold_style)
            ],
            [
                Paragraph("<b>Average Pulse:</b>", cell_style), Paragraph(f"{avg_pulse} bpm", cell_bold_style),
                Paragraph("<b>Peak Systolic:</b>", cell_style), Paragraph(f"{max_sys} mmHg", cell_bold_style),
                Paragraph("<b>Peak Diastolic:</b>", cell_style), Paragraph(f"{max_dia} mmHg", cell_bold_style)
            ],
            [
                Paragraph("", cell_style), Paragraph("", cell_style),
                Paragraph("<b>Min Systolic:</b>", cell_style), Paragraph(f"{min_sys} mmHg", cell_bold_style),
                Paragraph("<b>Min Diastolic:</b>", cell_style), Paragraph(f"{min_dia} mmHg", cell_bold_style)
            ]
        ]
        
        stats_table = Table(stats_data, colWidths=[100, 50, 110, 70, 110, 70])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
            ('PADDING', (0,0), (-1,-1), 8),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 15))

        # 3. Vector Chart
        story.append(Paragraph("Blood Pressure Trends", h2_style))
        # Show last 30 records maximum on the chart to prevent it from getting messy
        chart_records = records[-30:] if len(records) > 30 else records
        story.append(cls.draw_vector_chart(chart_records))
        story.append(Spacer(1, 15))

        # 4. History Table
        story.append(Paragraph("Reading Log History", h2_style))
        
        # Build headers
        history_data = [[
            Paragraph("<b>Date & Time</b>", cell_bold_style),
            Paragraph("<b>Systolic</b>", cell_bold_style),
            Paragraph("<b>Diastolic</b>", cell_bold_style),
            Paragraph("<b>Pulse</b>", cell_bold_style),
            Paragraph("<b>Category</b>", cell_bold_style),
            Paragraph("<b>Notes</b>", cell_bold_style)
        ]]

        # Populate rows
        # Chronological descending order for log table (latest readings first)
        sorted_history = sorted(records, key=lambda x: x['timestamp'], reverse=True)
        
        for r in sorted_history:
            sys = r['systolic']
            dia = r['diastolic']
            pulse = r['pulse'] if r['pulse'] is not None else "-"
            note = r['note'] if r['note'] else ""
            
            cat, cat_col = cls.get_bp_category(sys, dia)
            cat_p = Paragraph(f"<font color='{cat_col.hexval()}'><b>{cat}</b></font>", cell_style)
            
            history_data.append([
                Paragraph(r['timestamp'][:16], cell_style),
                Paragraph(f"{sys} mmHg", cell_style),
                Paragraph(f"{dia} mmHg", cell_style),
                Paragraph(f"{pulse}", cell_style),
                cat_p,
                Paragraph(note, cell_style)
            ])

        history_table = Table(history_data, colWidths=[100, 65, 65, 45, 110, 125])
        
        # Style table with alternating row colors
        t_style = [
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E2E8F0")),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,0), 8),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ]
        
        for idx in range(1, len(history_data)):
            if idx % 2 == 0:
                t_style.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#F8FAFC")))
                
        history_table.setStyle(TableStyle(t_style))
        story.append(history_table)

        # Build document
        doc.build(story)
        return filepath
