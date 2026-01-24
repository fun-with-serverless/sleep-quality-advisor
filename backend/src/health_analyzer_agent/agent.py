"""
Health Analyzer Agent - Sleep Quality Analysis with Environmental Correlations

Uses Strands framework with Claude Sonnet 4 to analyze weekly sleep data
and generate personalized insights based on environmental factors.
"""

import json
import os
from typing import Any, cast

from strands import Agent
from strands.models.bedrock import BedrockModel


class HealthAnalyzerAgent:
    """Agent for analyzing sleep health data and generating weekly reports."""

    SYSTEM_PROMPT = """You are an expert sleep health analyst specializing in correlating sleep quality \
with environmental factors.

Your role is to analyze weekly sleep data and provide personalized, actionable insights.

Available data sources (via MCP tools):
- Sleep sessions: Duration, stages (Deep, REM, Light, Awake), efficiency, scores
- Environmental readings: Temperature, humidity, atmospheric pressure, light levels, air quality, noise
- Historical comparisons: Week-over-week trends

Your analysis should be:
1. Data-driven: Base insights on actual measurements and correlations
2. Personalized: Identify this user's optimal conditions (not generic advice)
3. Actionable: Provide specific, practical recommendations
4. Comprehensive: Cover quantity, quality, patterns, and environmental factors
5. Comparative: Show improvements or regressions vs previous week

Analysis Structure:

## 1. Sleep Quantity Metrics
- Total hours slept during the week
- Average sleep duration per night
- Longest and shortest sleep nights
- Sleep consistency score (how regular is the schedule)
- Comparison to recommended 7-9 hours

## 2. Sleep Quality Insights
- Average sleep efficiency and scores
- Sleep stages distribution (Deep, REM, Light percentages)
- Deep sleep analysis: total hours, percentage, trend
- REM sleep analysis: total hours, percentage, trend
- Light sleep vs Awake time patterns

## 3. Sleep Pattern Analysis
- Bedtime consistency: average time, variance across week
- Wake time consistency: average time, variance
- Sleep debt calculation (cumulative deficit vs 7-9 hour target)
- Irregularities or concerning patterns

## 4. Environmental Correlations (CRITICAL ANALYSIS)
For EACH environmental factor, analyze the correlation with sleep quality:

**Temperature:**
- Identify optimal temperature range for THIS user based on their best sleep nights
- Note nights with suboptimal temperature and impact on sleep quality
- Specific recommendation with temperature range

**Humidity:**
- Analyze humidity levels during best vs worst sleep nights
- Identify optimal humidity range for THIS user
- Impact on deep sleep and overall efficiency

**Light Exposure:**
- Assess light levels during sleep hours
- Flag any light disruptions (spikes during sleep)
- Correlation with sleep quality and awake time

**Air Quality (if available):**
- Analyze IAQ during sleep hours
- Correlation with deep sleep and overall quality

**Noise (if available):**
- Identify noise disturbances during sleep
- Impact on sleep fragmentation and quality

## 5. Actionable Recommendations
Provide 2-3 SPECIFIC recommendations based on THIS user's data:
- NOT generic advice like "maintain consistent schedule"
- SPECIFIC like "Your best sleep (avg score 87) occurred when bedroom temp was 18-19°C.
  Consider setting thermostat to 18°C"
- Include the data that supports each recommendation

## 6. Week-over-Week Comparison
Compare to previous week:
- Changes in sleep duration, efficiency, scores
- Improvements or regressions in sleep stages
- Environmental factor changes and their impact
- Overall trend assessment

Output Format:
Return your analysis as a structured JSON object with these sections:
{
  "executive_summary": {
    "key_highlights": ["bullet point 1", "bullet point 2", "bullet point 3"]
  },
  "sleep_quantity": {
    "total_hours": float,
    "avg_hours_per_night": float,
    "longest_night": {"date": str, "hours": float},
    "shortest_night": {"date": str, "hours": float},
    "consistency_score": float,
    "vs_recommended": str
  },
  "sleep_quality": {
    "avg_efficiency": float,
    "avg_score": float,
    "deep_sleep": {"total_hours": float, "avg_percent": float, "trend": str},
    "rem_sleep": {"total_hours": float, "avg_percent": float, "trend": str},
    "light_sleep": {"total_hours": float, "avg_percent": float},
    "awake_time": {"total_hours": float, "avg_percent": float}
  },
  "sleep_patterns": {
    "bedtime_avg": str,
    "bedtime_variance": str,
    "wake_time_avg": str,
    "wake_time_variance": str,
    "sleep_debt": {"hours": float, "description": str}
  },
  "environmental_correlations": {
    "temperature": {
      "optimal_range": str,
      "correlation": str,
      "impact": str
    },
    "humidity": {
      "optimal_range": str,
      "correlation": str,
      "impact": str
    },
    "light": {
      "avg_during_sleep": float,
      "disruptions": str,
      "impact": str
    },
    "air_quality": {
      "avg_iaq": float,
      "correlation": str,
      "impact": str
    },
    "noise": {
      "avg_db": float,
      "disruptions": str,
      "impact": str
    }
  },
  "recommendations": [
    {
      "priority": int,
      "category": str,
      "recommendation": str,
      "supporting_data": str
    }
  ],
  "week_comparison": {
    "sleep_duration_change": {"hours": float, "trend": str},
    "efficiency_change": {"points": float, "trend": str},
    "score_change": {"points": float, "trend": str},
    "deep_sleep_change": {"minutes": float, "trend": str},
    "overall_assessment": str
  }
}

Remember: Focus on THIS user's specific data and patterns, not generic sleep advice."""

    def __init__(self) -> None:
        """Initialize the Health Analyzer Agent with Bedrock Claude Sonnet 4."""

        # Initialize Bedrock model
        self.model = BedrockModel(
            model_id=os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-sonnet-4-20250514-v1:0'),
            region_name=os.environ.get('AWS_REGION', 'us-east-1'),
            max_tokens=4096,
        )

        # MCP tools will be dynamically registered by AgentCore Runtime
        # when it connects to the MCP server Lambda

        self.agent: Agent | None = None

    def create_agent(self, mcp_tools: list) -> Agent:
        """
        Create the Strands agent with MCP tools.

        Args:
            mcp_tools: List of MCP tools from the MCP server

        Returns:
            Configured Strands Agent instance
        """
        self.agent = Agent(
            model=self.model,
            tools=mcp_tools,
            system_prompt=self.SYSTEM_PROMPT,
        )
        return self.agent

    def analyze_week(self, start_date: str, end_date: str) -> dict[str, Any]:
        """
        Generate weekly sleep health report.

        Args:
            start_date: Start date (YYYY-MM-DD, typically Monday)
            end_date: End date (YYYY-MM-DD, typically Sunday)

        Returns:
            Dictionary containing the complete analysis
        """
        if not self.agent:
            raise RuntimeError("Agent not initialized. Call create_agent() first.")

        prompt = f"""Generate a comprehensive weekly sleep health report for the period {start_date} to {end_date}.

Use the available MCP tools to:
1. Query sleep data for all nights in this period
2. Get summary statistics for the week
3. Query environmental data for the same period
4. For each night with sleep data, correlate environmental conditions during sleep hours
5. Compare this week to the previous week (calculate previous week dates)

Analyze all the data and return a structured JSON report following the format specified in your system prompt.

Be thorough in your analysis, especially the environmental correlations.
Identify specific patterns unique to this user."""

        # Invoke the agent
        response = self.agent(prompt)

        # Parse and return the response
        try:
            # Extract JSON from response if wrapped in markdown
            response_text = str(response)
            if '```json' in response_text:
                start = response_text.find('```json') + 7
                end = response_text.find('```', start)
                response_text = response_text[start:end].strip()
            elif '```' in response_text:
                start = response_text.find('```') + 3
                end = response_text.find('```', start)
                response_text = response_text[start:end].strip()

            analysis = json.loads(response_text)
            return cast(dict[str, Any], analysis)

        except json.JSONDecodeError as e:
            # If JSON parsing fails, return the raw response with error flag
            return {
                'error': 'Failed to parse agent response as JSON',
                'raw_response': str(response),
                'parse_error': str(e),
            }


def handler(event: Any, context: Any) -> dict[str, Any]:
    """
    Lambda handler for AgentCore Runtime invocations.

    This handler is called by AgentCore Runtime when the agent is invoked.
    It processes the request and returns the analysis.
    """
    try:
        # Parse input
        body = json.loads(event.get('body', '{}')) if isinstance(event.get('body'), str) else event

        start_date = body.get('start_date')
        end_date = body.get('end_date')

        if not start_date or not end_date:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Missing required parameters: start_date and end_date'}),
            }

        # Initialize agent
        # Note: In AgentCore Runtime, MCP tools are automatically injected
        # For now, we'll create a basic response structure

        HealthAnalyzerAgent()

        # In actual deployment, MCP tools would be injected by AgentCore
        # For this implementation, we'll return the configuration

        return {
            'statusCode': 200,
            'body': json.dumps(
                {
                    'message': 'Health Analyzer Agent initialized',
                    'model': os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-sonnet-4-20250514-v1:0'),
                    'start_date': start_date,
                    'end_date': end_date,
                    'status': 'ready',
                }
            ),
        }

    except Exception as e:
        return {'statusCode': 500, 'body': json.dumps({'error': str(e)})}


if __name__ == "__main__":
    """Local testing."""
    # For local testing, you would need to set up MCP client connection
    print("Health Analyzer Agent - Ready for AgentCore deployment")
    print(f"Model: {os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-sonnet-4-20250514-v1:0')}")
