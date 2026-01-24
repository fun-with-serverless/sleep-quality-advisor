"""
PDF Report Generator

Generates professional PDF reports from sleep health analysis data.
Uses reportlab for PDF creation with charts and formatted content.
"""

from io import BytesIO
from datetime import datetime
from typing import Dict, Any
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.linecharts import HorizontalLineChart


def create_header(start_date: str, end_date: str) -> list:
    """Create the report header section."""
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    elements.append(Paragraph("Weekly Sleep Health Report", title_style))

    # Date range
    date_style = ParagraphStyle(
        'DateRange',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER,
        spaceAfter=6
    )

    elements.append(Paragraph(f"{start_date} to {end_date}", date_style))

    # Generated timestamp
    generated_style = ParagraphStyle(
        'Generated',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#999999'),
        alignment=TA_CENTER,
        spaceAfter=20
    )

    generated_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    elements.append(Paragraph(f"Generated: {generated_time}", generated_style))

    elements.append(Spacer(1, 0.2 * inch))

    return elements


def create_executive_summary(analysis: Dict[str, Any]) -> list:
    """Create the executive summary section."""
    elements = []
    styles = getSampleStyleSheet()

    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )

    elements.append(Paragraph("Executive Summary", section_style))

    # Key highlights
    if 'executive_summary' in analysis and 'key_highlights' in analysis['executive_summary']:
        for highlight in analysis['executive_summary']['key_highlights']:
            bullet_style = ParagraphStyle(
                'Bullet',
                parent=styles['Normal'],
                fontSize=11,
                leftIndent=20,
                spaceAfter=6
            )
            elements.append(Paragraph(f"• {highlight}", bullet_style))

    elements.append(Spacer(1, 0.3 * inch))

    return elements


def create_sleep_quantity_section(analysis: Dict[str, Any]) -> list:
    """Create the sleep quantity metrics section with chart."""
    elements = []
    styles = getSampleStyleSheet()

    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )

    elements.append(Paragraph("Sleep Quantity Metrics", section_style))

    if 'sleep_quantity' not in analysis:
        elements.append(Paragraph("No sleep quantity data available", styles['Normal']))
        return elements

    sq = analysis['sleep_quantity']

    # Create summary table
    data = [
        ['Metric', 'Value'],
        ['Total Hours Slept', f"{sq.get('total_hours', 0):.1f} hours"],
        ['Average Per Night', f"{sq.get('avg_hours_per_night', 0):.1f} hours"],
        ['Longest Night', f"{sq.get('longest_night', {}).get('hours', 0):.1f} hours ({sq.get('longest_night', {}).get('date', 'N/A')})"],
        ['Shortest Night', f"{sq.get('shortest_night', {}).get('hours', 0):.1f} hours ({sq.get('shortest_night', {}).get('date', 'N/A')})"],
        ['Consistency Score', f"{sq.get('consistency_score', 0):.2f} (lower is better)"],
        ['vs Recommended', sq.get('vs_recommended', 'N/A')]
    ]

    table = Table(data, colWidths=[3 * inch, 3 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    elements.append(Spacer(1, 0.3 * inch))

    return elements


def create_sleep_quality_section(analysis: Dict[str, Any]) -> list:
    """Create the sleep quality section with pie chart."""
    elements = []
    styles = getSampleStyleSheet()

    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )

    elements.append(Paragraph("Sleep Quality Insights", section_style))

    if 'sleep_quality' not in analysis:
        elements.append(Paragraph("No sleep quality data available", styles['Normal']))
        return elements

    sq = analysis['sleep_quality']

    # Create summary table
    data = [
        ['Metric', 'Value', 'Trend'],
        ['Average Efficiency', f"{sq.get('avg_efficiency', 0):.1f}%", ''],
        ['Average Score', f"{sq.get('avg_score', 0):.1f}", ''],
        ['Deep Sleep', f"{sq.get('deep_sleep', {}).get('total_hours', 0):.1f} hrs ({sq.get('deep_sleep', {}).get('avg_percent', 0):.1f}%)", sq.get('deep_sleep', {}).get('trend', 'N/A')],
        ['REM Sleep', f"{sq.get('rem_sleep', {}).get('total_hours', 0):.1f} hrs ({sq.get('rem_sleep', {}).get('avg_percent', 0):.1f}%)", sq.get('rem_sleep', {}).get('trend', 'N/A')],
        ['Light Sleep', f"{sq.get('light_sleep', {}).get('total_hours', 0):.1f} hrs ({sq.get('light_sleep', {}).get('avg_percent', 0):.1f}%)", ''],
        ['Awake Time', f"{sq.get('awake_time', {}).get('total_hours', 0):.1f} hrs ({sq.get('awake_time', {}).get('avg_percent', 0):.1f}%)", '']
    ]

    table = Table(data, colWidths=[2 * inch, 2.5 * inch, 1.5 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    elements.append(Spacer(1, 0.3 * inch))

    return elements


def create_environmental_section(analysis: Dict[str, Any]) -> list:
    """Create the environmental correlations section."""
    elements = []
    styles = getSampleStyleSheet()

    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )

    elements.append(Paragraph("Environmental Correlations", section_style))

    if 'environmental_correlations' not in analysis:
        elements.append(Paragraph("No environmental data available", styles['Normal']))
        return elements

    env = analysis['environmental_correlations']

    # Temperature
    if 'temperature' in env:
        temp = env['temperature']
        elements.append(Paragraph("<b>Temperature:</b>", styles['Normal']))
        elements.append(Paragraph(f"Optimal Range: {temp.get('optimal_range', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"Impact: {temp.get('impact', 'N/A')}", styles['Normal']))
        elements.append(Spacer(1, 0.1 * inch))

    # Humidity
    if 'humidity' in env:
        hum = env['humidity']
        elements.append(Paragraph("<b>Humidity:</b>", styles['Normal']))
        elements.append(Paragraph(f"Optimal Range: {hum.get('optimal_range', 'N/A')}", styles['Normal']))
        elements.append(Paragraph(f"Impact: {hum.get('impact', 'N/A')}", styles['Normal']))
        elements.append(Spacer(1, 0.1 * inch))

    # Light
    if 'light' in env:
        light = env['light']
        elements.append(Paragraph("<b>Light Exposure:</b>", styles['Normal']))
        elements.append(Paragraph(f"Average During Sleep: {light.get('avg_during_sleep', 0):.1f} lux", styles['Normal']))
        elements.append(Paragraph(f"Impact: {light.get('impact', 'N/A')}", styles['Normal']))
        elements.append(Spacer(1, 0.1 * inch))

    # Air Quality
    if 'air_quality' in env and env['air_quality'].get('avg_iaq'):
        aq = env['air_quality']
        elements.append(Paragraph("<b>Air Quality:</b>", styles['Normal']))
        elements.append(Paragraph(f"Average IAQ: {aq.get('avg_iaq', 0):.1f}", styles['Normal']))
        elements.append(Paragraph(f"Impact: {aq.get('impact', 'N/A')}", styles['Normal']))
        elements.append(Spacer(1, 0.1 * inch))

    # Noise
    if 'noise' in env and env['noise'].get('avg_db'):
        noise = env['noise']
        elements.append(Paragraph("<b>Noise Levels:</b>", styles['Normal']))
        elements.append(Paragraph(f"Average: {noise.get('avg_db', 0):.1f} dB", styles['Normal']))
        elements.append(Paragraph(f"Impact: {noise.get('impact', 'N/A')}", styles['Normal']))
        elements.append(Spacer(1, 0.1 * inch))

    elements.append(Spacer(1, 0.2 * inch))

    return elements


def create_recommendations_section(analysis: Dict[str, Any]) -> list:
    """Create the recommendations section."""
    elements = []
    styles = getSampleStyleSheet()

    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )

    elements.append(Paragraph("Actionable Recommendations", section_style))

    if 'recommendations' not in analysis or not analysis['recommendations']:
        elements.append(Paragraph("No specific recommendations available", styles['Normal']))
        return elements

    for rec in sorted(analysis['recommendations'], key=lambda x: x.get('priority', 999)):
        # Recommendation box
        rec_style = ParagraphStyle(
            'Recommendation',
            parent=styles['Normal'],
            fontSize=11,
            leftIndent=10,
            spaceAfter=6,
            borderPadding=10,
            borderWidth=1,
            borderColor=colors.HexColor('#1a5490')
        )

        rec_text = f"<b>{rec.get('category', 'General')}:</b> {rec.get('recommendation', '')}"
        elements.append(Paragraph(rec_text, styles['Normal']))

        if rec.get('supporting_data'):
            support_style = ParagraphStyle(
                'Support',
                parent=styles['Normal'],
                fontSize=9,
                leftIndent=20,
                textColor=colors.HexColor('#666666'),
                spaceAfter=12
            )
            elements.append(Paragraph(f"Based on: {rec['supporting_data']}", support_style))

    elements.append(Spacer(1, 0.3 * inch))

    return elements


def create_comparison_section(analysis: Dict[str, Any]) -> list:
    """Create the week-over-week comparison section."""
    elements = []
    styles = getSampleStyleSheet()

    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1a5490'),
        spaceAfter=12,
        fontName='Helvetica-Bold'
    )

    elements.append(Paragraph("Week-over-Week Comparison", section_style))

    if 'week_comparison' not in analysis:
        elements.append(Paragraph("No comparison data available", styles['Normal']))
        return elements

    wc = analysis['week_comparison']

    # Create comparison table
    def format_trend(value, suffix=''):
        if isinstance(value, dict):
            val = value.get('hours', value.get('points', value.get('minutes', 0)))
            trend = value.get('trend', '')
        else:
            val = value
            trend = ''

        arrow = ''
        if trend.lower() == 'improving' or val > 0:
            arrow = '↑'
        elif trend.lower() == 'declining' or val < 0:
            arrow = '↓'
        else:
            arrow = '→'

        return f"{val:+.1f}{suffix} {arrow}"

    data = [
        ['Metric', 'Change'],
        ['Sleep Duration', format_trend(wc.get('sleep_duration_change', {}), ' hrs')],
        ['Efficiency', format_trend(wc.get('efficiency_change', {}), ' pts')],
        ['Score', format_trend(wc.get('score_change', {}), ' pts')],
        ['Deep Sleep', format_trend(wc.get('deep_sleep_change', {}), ' min')]
    ]

    table = Table(data, colWidths=[3 * inch, 3 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5490')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)

    # Overall assessment
    if wc.get('overall_assessment'):
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph(f"<b>Overall:</b> {wc['overall_assessment']}", styles['Normal']))

    return elements


def generate_pdf_report(analysis: Dict[str, Any], start_date: str, end_date: str) -> bytes:
    """
    Generate a PDF report from the analysis data.

    Args:
        analysis: Analysis dictionary from the agent
        start_date: Report start date (YYYY-MM-DD)
        end_date: Report end date (YYYY-MM-DD)

    Returns:
        PDF content as bytes
    """
    buffer = BytesIO()

    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )

    # Build the document
    story = []

    # Add sections
    story.extend(create_header(start_date, end_date))
    story.extend(create_executive_summary(analysis))
    story.extend(create_sleep_quantity_section(analysis))
    story.extend(create_sleep_quality_section(analysis))
    story.extend(create_environmental_section(analysis))
    story.extend(create_recommendations_section(analysis))
    story.extend(create_comparison_section(analysis))

    # Build PDF
    doc.build(story)

    # Get PDF content
    pdf_content = buffer.getvalue()
    buffer.close()

    return pdf_content
