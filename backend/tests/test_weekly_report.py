"""Unit tests for Weekly Report Orchestrator Lambda."""

import contextlib
import json
import os
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import boto3
import pytest

from src.weekly_report.handler import calculate_week_dates, get_recipient_email, lambda_handler

from .utils import FakeLambdaContext


def test_calculate_week_dates_monday() -> None:
    """Test week calculation when today is Monday."""
    # Mock datetime to return a specific Monday
    with patch("src.weekly_report.handler.datetime") as mock_datetime:
        # Set "today" to Monday 2025-01-20
        mock_datetime.utcnow.return_value.date.return_value = datetime(2025, 1, 20).date()
        mock_datetime.return_value = datetime(2025, 1, 20)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        start, end = calculate_week_dates()

        # Should return previous week: Mon 2025-01-13 to Sun 2025-01-19
        assert start == "2025-01-13"
        assert end == "2025-01-19"


def test_calculate_week_dates_wednesday() -> None:
    """Test week calculation when today is Wednesday."""
    with patch("src.weekly_report.handler.datetime") as mock_datetime:
        # Set "today" to Wednesday 2025-01-22
        mock_datetime.utcnow.return_value.date.return_value = datetime(2025, 1, 22).date()
        mock_datetime.return_value = datetime(2025, 1, 22)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        start, end = calculate_week_dates()

        # Should return previous week: Mon 2025-01-13 to Sun 2025-01-19
        assert start == "2025-01-13"
        assert end == "2025-01-19"


def test_calculate_week_dates_sunday() -> None:
    """Test week calculation when today is Sunday."""
    with patch("src.weekly_report.handler.datetime") as mock_datetime:
        # Set "today" to Sunday 2025-01-19
        mock_datetime.utcnow.return_value.date.return_value = datetime(2025, 1, 19).date()
        mock_datetime.return_value = datetime(2025, 1, 19)
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        start, end = calculate_week_dates()

        # Should return previous week: Mon 2025-01-06 to Sun 2025-01-12
        assert start == "2025-01-06"
        assert end == "2025-01-12"


def test_get_recipient_email_success(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    """Test retrieving email from SSM."""
    # Create SSM parameter
    ssm = boto3.client("ssm")
    ssm.put_parameter(Name="/sleep-advisor/report-email", Type="String", Value="test@example.com", Overwrite=True)

    email = get_recipient_email()

    assert email == "test@example.com"


def test_get_recipient_email_not_configured(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    """Test retrieving email when parameter exists but has default value."""
    ssm = boto3.client("ssm")
    ssm.put_parameter(Name="/sleep-advisor/report-email", Type="String", Value="changeme@example.com", Overwrite=True)

    with pytest.raises(ValueError, match="Email not configured"):
        get_recipient_email()


def test_get_recipient_email_parameter_not_found(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    """Test retrieving email when SSM parameter doesn't exist."""
    # Delete the parameter that was created in conftest
    ssm = boto3.client("ssm")
    with contextlib.suppress(Exception):
        ssm.delete_parameter(Name="/sleep-advisor/report-email")

    with pytest.raises(ValueError, match="SSM parameter not found"):
        get_recipient_email()


def test_get_recipient_email_custom_parameter(aws_moto: None) -> None:  # type: ignore[unused-ignore]
    """Test retrieving email from custom parameter name."""
    ssm = boto3.client("ssm")
    ssm.put_parameter(Name="/custom/email/path", Type="String", Value="custom@example.com", Overwrite=True)

    os.environ["EMAIL_PARAMETER_NAME"] = "/custom/email/path"
    try:
        email = get_recipient_email()
        assert email == "custom@example.com"
    finally:
        del os.environ["EMAIL_PARAMETER_NAME"]


@patch("src.weekly_report.handler.invoke_agent")
@patch("src.weekly_report.handler.generate_pdf_report")
@patch("src.weekly_report.handler.send_email_with_pdf")
@patch("src.weekly_report.handler.get_recipient_email")
@patch("src.weekly_report.handler.calculate_week_dates")
def test_lambda_handler_success(
    mock_calc_dates: MagicMock,
    mock_get_email: MagicMock,
    mock_send_email: MagicMock,
    mock_gen_pdf: MagicMock,
    mock_invoke: MagicMock,
    aws_moto: None,  # type: ignore[unused-ignore]
) -> None:
    """Test successful Lambda execution."""
    # Setup mocks
    mock_calc_dates.return_value = ("2025-01-13", "2025-01-19")
    mock_get_email.return_value = "test@example.com"

    mock_analysis: dict[str, Any] = {
        "executive_summary": {"key_highlights": ["Test highlight"]},
        "sleep_quantity": {"total_hours": 50.0},
    }
    mock_invoke.return_value = mock_analysis

    mock_gen_pdf.return_value = b"%PDF-1.4 test content"

    # Execute
    event = {}
    context = FakeLambdaContext()

    result = lambda_handler(event, context)

    # Assertions
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["message"] == "Weekly report sent successfully"
    assert body["start_date"] == "2025-01-13"
    assert body["end_date"] == "2025-01-19"
    assert body["recipient"] == "test@example.com"

    # Verify all functions were called
    mock_calc_dates.assert_called_once()
    mock_invoke.assert_called_once_with("2025-01-13", "2025-01-19")
    mock_gen_pdf.assert_called_once()
    mock_send_email.assert_called_once()


@patch("src.weekly_report.handler.invoke_agent")
@patch("src.weekly_report.handler.calculate_week_dates")
def test_lambda_handler_agent_error(
    mock_calc_dates: MagicMock,
    mock_invoke: MagicMock,
    aws_moto: None,  # type: ignore[unused-ignore]
) -> None:
    """Test Lambda execution when agent returns error."""
    mock_calc_dates.return_value = ("2025-01-13", "2025-01-19")

    # Agent returns error
    mock_invoke.return_value = {"error": "Agent failed to analyze data"}

    event = {}
    context = FakeLambdaContext()

    result = lambda_handler(event, context)

    # Should return error status
    assert result["statusCode"] == 500
    body = json.loads(result["body"])
    assert "error" in body


@patch("src.weekly_report.handler.invoke_agent")
@patch("src.weekly_report.handler.calculate_week_dates")
def test_lambda_handler_invocation_exception(
    mock_calc_dates: MagicMock,
    mock_invoke: MagicMock,
    aws_moto: None,  # type: ignore[unused-ignore]
) -> None:
    """Test Lambda execution when agent invocation raises exception."""
    mock_calc_dates.return_value = ("2025-01-13", "2025-01-19")

    # Agent invocation raises exception
    mock_invoke.side_effect = Exception("Bedrock AgentCore unavailable")

    event = {}
    context = FakeLambdaContext()

    result = lambda_handler(event, context)

    # Should return error status
    assert result["statusCode"] == 500
    body = json.loads(result["body"])
    assert "error" in body


@patch("src.weekly_report.handler.invoke_agent")
@patch("src.weekly_report.handler.generate_pdf_report")
@patch("src.weekly_report.handler.get_recipient_email")
@patch("src.weekly_report.handler.calculate_week_dates")
def test_lambda_handler_pdf_generation_error(
    mock_calc_dates: MagicMock,
    mock_get_email: MagicMock,
    mock_gen_pdf: MagicMock,
    mock_invoke: MagicMock,
    aws_moto: None,  # type: ignore[unused-ignore]
) -> None:
    """Test Lambda execution when PDF generation fails."""
    mock_calc_dates.return_value = ("2025-01-13", "2025-01-19")
    mock_get_email.return_value = "test@example.com"
    mock_invoke.return_value = {"sleep_quantity": {"total_hours": 50.0}}

    # PDF generation fails
    mock_gen_pdf.side_effect = Exception("PDF generation failed")

    event = {}
    context = FakeLambdaContext()

    result = lambda_handler(event, context)

    # Should return error status
    assert result["statusCode"] == 500
    body = json.loads(result["body"])
    assert "error" in body


@patch("src.weekly_report.handler.invoke_agent")
@patch("src.weekly_report.handler.generate_pdf_report")
@patch("src.weekly_report.handler.send_email_with_pdf")
@patch("src.weekly_report.handler.get_recipient_email")
@patch("src.weekly_report.handler.calculate_week_dates")
def test_lambda_handler_email_sending_error(
    mock_calc_dates: MagicMock,
    mock_get_email: MagicMock,
    mock_send_email: MagicMock,
    mock_gen_pdf: MagicMock,
    mock_invoke: MagicMock,
    aws_moto: None,  # type: ignore[unused-ignore]
) -> None:
    """Test Lambda execution when email sending fails."""
    mock_calc_dates.return_value = ("2025-01-13", "2025-01-19")
    mock_get_email.return_value = "test@example.com"
    mock_invoke.return_value = {"sleep_quantity": {"total_hours": 50.0}}
    mock_gen_pdf.return_value = b"%PDF-1.4 test"

    # Email sending fails
    mock_send_email.side_effect = Exception("SES error: Email not verified")

    event = {}
    context = FakeLambdaContext()

    result = lambda_handler(event, context)

    # Should return error status
    assert result["statusCode"] == 500
    body = json.loads(result["body"])
    assert "error" in body
