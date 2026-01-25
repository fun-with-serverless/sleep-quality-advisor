"""Unit tests for Health Analyzer Agent.

Note: These tests cover basic functionality and configuration.
Full agent testing requires Strands framework and is better suited for integration tests.
"""

import json
import os

import pytest

from src.health_analyzer_agent.agent import HealthAnalyzerAgent, handler

from .utils import FakeLambdaContext


def test_health_analyzer_agent_initialization() -> None:
    """Test Health Analyzer Agent initialization."""
    # Set required environment variables
    os.environ["BEDROCK_MODEL_ID"] = "anthropic.claude-sonnet-4-20250514-v1:0"
    os.environ["AWS_REGION"] = "us-east-1"

    try:
        agent = HealthAnalyzerAgent()

        assert agent is not None
        assert agent.model is not None
        assert agent.agent is None  # Not initialized until create_agent is called
    finally:
        # Cleanup
        if "BEDROCK_MODEL_ID" in os.environ:
            del os.environ["BEDROCK_MODEL_ID"]
        if "AWS_REGION" in os.environ:
            del os.environ["AWS_REGION"]


def test_health_analyzer_agent_default_config() -> None:
    """Test Health Analyzer Agent with default configuration."""
    # Don't set environment variables, should use defaults
    if "BEDROCK_MODEL_ID" in os.environ:
        del os.environ["BEDROCK_MODEL_ID"]
    if "AWS_REGION" in os.environ:
        del os.environ["AWS_REGION"]

    agent = HealthAnalyzerAgent()

    assert agent is not None
    # Should use default model and region
    assert agent.model is not None


def test_health_analyzer_agent_system_prompt() -> None:
    """Test that the agent has a proper system prompt."""
    HealthAnalyzerAgent()

    assert HealthAnalyzerAgent.SYSTEM_PROMPT is not None
    assert len(HealthAnalyzerAgent.SYSTEM_PROMPT) > 100

    # Check for key components in the prompt
    assert "sleep health analyst" in HealthAnalyzerAgent.SYSTEM_PROMPT.lower()
    assert "environmental" in HealthAnalyzerAgent.SYSTEM_PROMPT.lower()
    assert "temperature" in HealthAnalyzerAgent.SYSTEM_PROMPT.lower()
    assert "humidity" in HealthAnalyzerAgent.SYSTEM_PROMPT.lower()
    assert "recommendations" in HealthAnalyzerAgent.SYSTEM_PROMPT.lower()


def test_handler_missing_parameters() -> None:
    """Test handler with missing required parameters."""
    event = {"body": json.dumps({})}
    context = FakeLambdaContext()

    result = handler(event, context)

    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "error" in body
    assert "start_date" in body["error"] or "end_date" in body["error"]


def test_handler_with_required_parameters() -> None:
    """Test handler with all required parameters."""
    os.environ["BEDROCK_MODEL_ID"] = "anthropic.claude-sonnet-4-20250514-v1:0"

    try:
        event = {"body": json.dumps({"start_date": "2025-01-13", "end_date": "2025-01-19"})}
        context = FakeLambdaContext()

        result = handler(event, context)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "Health Analyzer Agent initialized"
        assert body["start_date"] == "2025-01-13"
        assert body["end_date"] == "2025-01-19"
        assert body["status"] == "ready"
    finally:
        if "BEDROCK_MODEL_ID" in os.environ:
            del os.environ["BEDROCK_MODEL_ID"]


def test_handler_with_dict_body() -> None:
    """Test handler when body is already a dict (not JSON string)."""
    os.environ["BEDROCK_MODEL_ID"] = "anthropic.claude-sonnet-4-20250514-v1:0"

    try:
        event = {"start_date": "2025-01-13", "end_date": "2025-01-19"}
        context = FakeLambdaContext()

        result = handler(event, context)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["start_date"] == "2025-01-13"
    finally:
        if "BEDROCK_MODEL_ID" in os.environ:
            del os.environ["BEDROCK_MODEL_ID"]


def test_handler_exception_handling() -> None:
    """Test handler exception handling."""
    # Trigger an exception by providing invalid event structure
    event = None  # type: ignore[assignment]
    context = FakeLambdaContext()

    result = handler(event, context)  # type: ignore[arg-type]

    assert result["statusCode"] == 500
    body = json.loads(result["body"])
    assert "error" in body


def test_analyze_week_without_agent_initialized() -> None:
    """Test analyze_week raises error when agent not initialized."""
    agent = HealthAnalyzerAgent()

    with pytest.raises(RuntimeError, match="Agent not initialized"):
        agent.analyze_week("2025-01-13", "2025-01-19")
