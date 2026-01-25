"""Unit tests for PDF Generator."""

from typing import Any

import pytest

from src.weekly_report.pdf_generator import (
    create_comparison_section,
    create_environmental_section,
    create_executive_summary,
    create_header,
    create_recommendations_section,
    create_sleep_quality_section,
    create_sleep_quantity_section,
    generate_pdf_report,
)


@pytest.fixture
def sample_analysis() -> dict[str, Any]:
    """Sample analysis data for testing."""
    return {
        "executive_summary": {
            "key_highlights": [
                "You averaged 7.5 hours of sleep per night this week",
                "Deep sleep improved by 15 minutes compared to last week",
                "Optimal bedroom temperature was 19°C on your best nights",
            ]
        },
        "sleep_quantity": {
            "total_hours": 52.5,
            "avg_hours_per_night": 7.5,
            "longest_night": {"date": "2025-01-14", "hours": 8.5},
            "shortest_night": {"date": "2025-01-16", "hours": 6.8},
            "consistency_score": 0.45,
            "vs_recommended": "Within recommended range",
        },
        "sleep_quality": {
            "avg_efficiency": 87.2,
            "avg_score": 82.5,
            "deep_sleep": {"total_hours": 12.5, "avg_percent": 18.5, "trend": "improving"},
            "rem_sleep": {"total_hours": 15.0, "avg_percent": 22.0, "trend": "stable"},
            "light_sleep": {"total_hours": 20.0, "avg_percent": 45.0},
            "awake_time": {"total_hours": 5.0, "avg_percent": 14.5},
        },
        "sleep_patterns": {
            "bedtime_avg": "23:15",
            "bedtime_variance": "±45 minutes",
            "wake_time_avg": "07:00",
            "wake_time_variance": "±30 minutes",
            "sleep_debt": {"hours": 1.5, "description": "Mild sleep debt accumulated"},
        },
        "environmental_correlations": {
            "temperature": {
                "optimal_range": "18-20°C",
                "correlation": "Strong positive correlation with deep sleep",
                "impact": "Best sleep occurred when temperature was 18-20°C",
            },
            "humidity": {
                "optimal_range": "45-55%",
                "correlation": "Moderate positive correlation",
                "impact": "Nights with humidity 45-55% showed better efficiency",
            },
            "light": {
                "avg_during_sleep": 2.5,
                "disruptions": "Light exposure detected at 3 AM on 2 nights",
                "impact": "Reduced sleep efficiency on nights with light disruptions",
            },
            "air_quality": {"avg_iaq": 45.0, "correlation": "Good", "impact": "Good air quality throughout the week"},
            "noise": {"avg_db": 35.0, "disruptions": "None detected", "impact": "Quiet environment maintained"},
        },
        "recommendations": [
            {
                "priority": 1,
                "category": "Temperature",
                "recommendation": "Maintain bedroom temperature at 19°C for optimal deep sleep",
                "supporting_data": "Your 3 best nights all had temperatures between 18-20°C",
            },
            {
                "priority": 2,
                "category": "Light",
                "recommendation": "Address light leak around 3 AM - consider blackout curtains",
                "supporting_data": "Light exposure detected on 2 nights, correlating with reduced efficiency",
            },
            {
                "priority": 3,
                "category": "Schedule",
                "recommendation": "Try going to bed within 30 minutes of 23:00 for better consistency",
                "supporting_data": "Bedtime variance of ±45 minutes, aim for tighter window",
            },
        ],
        "week_comparison": {
            "sleep_duration_change": {"hours": 0.8, "trend": "improving"},
            "efficiency_change": {"points": 3.5, "trend": "improving"},
            "score_change": {"points": 5.2, "trend": "improving"},
            "deep_sleep_change": {"minutes": 15.0, "trend": "improving"},
            "overall_assessment": "Significant improvement across all metrics this week",
        },
    }


def test_create_header() -> None:
    """Test PDF header creation."""
    elements = create_header("2025-01-13", "2025-01-19")

    assert len(elements) > 0
    # Should have title, date range, and generated timestamp
    assert len(elements) >= 4  # Title, date, generated time, spacer


def test_create_executive_summary(sample_analysis: dict[str, Any]) -> None:
    """Test executive summary section."""
    elements = create_executive_summary(sample_analysis)

    assert len(elements) > 0
    # Should have section heading + 3 highlights + spacer
    assert len(elements) >= 4


def test_create_executive_summary_no_data() -> None:
    """Test executive summary with no data."""
    elements = create_executive_summary({})

    # Should still create a section, even if empty
    assert len(elements) > 0


def test_create_sleep_quantity_section(sample_analysis: dict[str, Any]) -> None:
    """Test sleep quantity section."""
    elements = create_sleep_quantity_section(sample_analysis)

    assert len(elements) > 0
    # Should have heading, table, spacer
    assert len(elements) >= 3


def test_create_sleep_quantity_section_no_data() -> None:
    """Test sleep quantity section with no data."""
    elements = create_sleep_quantity_section({})

    # Should have heading and "no data" message
    assert len(elements) >= 2


def test_create_sleep_quality_section(sample_analysis: dict[str, Any]) -> None:
    """Test sleep quality section."""
    elements = create_sleep_quality_section(sample_analysis)

    assert len(elements) > 0
    # Should have heading, table, spacer
    assert len(elements) >= 3


def test_create_sleep_quality_section_no_data() -> None:
    """Test sleep quality section with no data."""
    elements = create_sleep_quality_section({})

    # Should have heading and "no data" message
    assert len(elements) >= 2


def test_create_environmental_section(sample_analysis: dict[str, Any]) -> None:
    """Test environmental correlations section."""
    elements = create_environmental_section(sample_analysis)

    assert len(elements) > 0
    # Should have heading and multiple environmental factors
    assert len(elements) >= 10  # Heading + temp + humidity + light + air + noise + spacers


def test_create_environmental_section_partial_data() -> None:
    """Test environmental section with partial data."""
    partial_data = {
        "environmental_correlations": {
            "temperature": {"optimal_range": "18-20°C", "impact": "Good"},
            # Missing other factors
        }
    }

    elements = create_environmental_section(partial_data)

    assert len(elements) > 0
    # Should still create section with available data
    assert len(elements) >= 3


def test_create_environmental_section_no_data() -> None:
    """Test environmental section with no data."""
    elements = create_environmental_section({})

    # Should have heading and "no data" message
    assert len(elements) >= 2


def test_create_recommendations_section(sample_analysis: dict[str, Any]) -> None:
    """Test recommendations section."""
    elements = create_recommendations_section(sample_analysis)

    assert len(elements) > 0
    # Should have heading + 3 recommendations with supporting data
    assert len(elements) >= 7  # Heading + 3×(rec+support) + spacer


def test_create_recommendations_section_no_data() -> None:
    """Test recommendations section with no data."""
    elements = create_recommendations_section({})

    # Should have heading and "no recommendations" message
    assert len(elements) >= 2


def test_create_comparison_section(sample_analysis: dict[str, Any]) -> None:
    """Test week-over-week comparison section."""
    elements = create_comparison_section(sample_analysis)

    assert len(elements) > 0
    # Should have heading, table, overall assessment
    assert len(elements) >= 3


def test_create_comparison_section_no_data() -> None:
    """Test comparison section with no data."""
    elements = create_comparison_section({})

    # Should have heading and "no data" message
    assert len(elements) >= 2


def test_generate_pdf_report_success(sample_analysis: dict[str, Any]) -> None:
    """Test complete PDF generation."""
    pdf_bytes = generate_pdf_report(sample_analysis, "2025-01-13", "2025-01-19")

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0

    # PDF files start with %PDF
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_pdf_report_minimal_data() -> None:
    """Test PDF generation with minimal data."""
    minimal_data: dict[str, Any] = {}

    pdf_bytes = generate_pdf_report(minimal_data, "2025-01-13", "2025-01-19")

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF"


def test_generate_pdf_report_partial_data() -> None:
    """Test PDF generation with partial data."""
    partial_data = {
        "executive_summary": {"key_highlights": ["Test highlight"]},
        "sleep_quantity": {"total_hours": 50.0, "avg_hours_per_night": 7.14},
    }

    pdf_bytes = generate_pdf_report(partial_data, "2025-01-13", "2025-01-19")

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes[:4] == b"%PDF"
