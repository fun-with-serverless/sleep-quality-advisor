"""
Weekly Report Orchestrator Lambda

Triggered by EventBridge schedule, this Lambda:
1. Calculates the previous week's date range
2. Invokes the Health Analyzer Agent via AgentCore Runtime
3. Generates a PDF report from the analysis
4. Sends the report via SES to the configured email

"""

import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from pdf_generator import generate_pdf_report


# Initialize AWS clients
bedrock_agentcore = boto3.client('bedrock-agentcore', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
ssm = boto3.client('ssm', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
ses = boto3.client('ses', region_name=os.environ.get('AWS_REGION', 'us-east-1'))


def calculate_week_dates() -> tuple[str, str]:
    """
    Calculate the date range for the previous week (Monday to Sunday).

    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format
    """
    today = datetime.utcnow().date()

    # Calculate last Monday
    days_since_monday = (today.weekday() + 7) % 7  # 0 = Monday
    if days_since_monday == 0:
        # If today is Monday, go back 7 days to get last Monday
        last_monday = today - timedelta(days=7)
    else:
        # Go back to last Monday
        last_monday = today - timedelta(days=days_since_monday + 7)

    # Last Sunday is 6 days after last Monday
    last_sunday = last_monday + timedelta(days=6)

    return (
        last_monday.strftime("%Y-%m-%d"),
        last_sunday.strftime("%Y-%m-%d")
    )


def invoke_agent(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Invoke the Health Analyzer Agent via AgentCore Runtime.

    Args:
        start_date: Week start date (YYYY-MM-DD)
        end_date: Week end date (YYYY-MM-DD)

    Returns:
        Analysis results from the agent
    """
    agent_arn = os.environ['AGENT_ARN']
    session_id = str(uuid.uuid4())

    payload = json.dumps({
        "start_date": start_date,
        "end_date": end_date,
        "generate_report": True
    }).encode('utf-8')

    print(f"Invoking agent: {agent_arn}")
    print(f"Session ID: {session_id}")
    print(f"Date range: {start_date} to {end_date}")

    try:
        response = bedrock_agentcore.invoke_agent_runtime(
            agentRuntimeArn=agent_arn,
            runtimeSessionId=session_id,
            payload=payload
        )

        # Parse streaming response
        content = []
        response_body = response.get('response')

        if hasattr(response_body, 'read'):
            # Streaming response
            for chunk in response_body:
                if chunk:
                    content.append(chunk)

            # Combine chunks
            full_response = b''.join(content).decode('utf-8')

        elif isinstance(response_body, (list, tuple)):
            # Response as list/tuple
            for chunk in response_body:
                if isinstance(chunk, bytes):
                    content.append(chunk.decode('utf-8'))
                else:
                    content.append(str(chunk))

            full_response = ''.join(content)

        else:
            # Direct response
            if isinstance(response_body, bytes):
                full_response = response_body.decode('utf-8')
            else:
                full_response = str(response_body)

        print(f"Received response ({len(full_response)} chars)")

        # Parse JSON response
        try:
            analysis = json.loads(full_response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            if '```json' in full_response:
                start = full_response.find('```json') + 7
                end = full_response.find('```', start)
                full_response = full_response[start:end].strip()
            elif '```' in full_response:
                start = full_response.find('```') + 3
                end = full_response.find('```', start)
                full_response = full_response[start:end].strip()

            analysis = json.loads(full_response)

        return analysis

    except Exception as e:
        print(f"Error invoking agent: {str(e)}")
        raise


def get_recipient_email() -> str:
    """
    Retrieve the recipient email address from SSM Parameter Store.

    Returns:
        Email address string
    """
    param_name = os.environ.get('EMAIL_PARAMETER_NAME', '/sleep-advisor/report-email')

    try:
        response = ssm.get_parameter(Name=param_name)
        email = response['Parameter']['Value']

        if not email or email == 'changeme@example.com':
            raise ValueError(f"Email not configured in SSM parameter: {param_name}")

        return email

    except ssm.exceptions.ParameterNotFound:
        raise ValueError(f"SSM parameter not found: {param_name}")
    except Exception as e:
        print(f"Error retrieving email from SSM: {str(e)}")
        raise


def send_email_with_pdf(
    recipient: str,
    pdf_content: bytes,
    start_date: str,
    end_date: str,
    analysis: Dict[str, Any]
) -> None:
    """
    Send the weekly report via SES with PDF attachment.

    Args:
        recipient: Email address to send to
        pdf_content: PDF file content (bytes)
        start_date: Report start date
        end_date: Report end date
        analysis: Analysis data for email body
    """
    sender = os.environ.get('SENDER_EMAIL', recipient)  # Use recipient as sender (must be verified)
    subject = f"Weekly Sleep Health Report - {start_date} to {end_date}"

    # Create email
    msg = MIMEMultipart('mixed')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    # Email body (plain text)
    body_text = f"""Your Weekly Sleep Health Report is attached.

Report Period: {start_date} to {end_date}

Executive Summary:
"""

    # Add key highlights if available
    if 'executive_summary' in analysis and 'key_highlights' in analysis['executive_summary']:
        for highlight in analysis['executive_summary']['key_highlights']:
            body_text += f"• {highlight}\n"

    body_text += "\nPlease see the attached PDF for your complete sleep health analysis.\n\n"
    body_text += "This report was automatically generated by your Sleep Quality Advisor system.\n"

    # Attach body
    body_part = MIMEText(body_text, 'plain')
    msg.attach(body_part)

    # Attach PDF
    pdf_part = MIMEApplication(pdf_content, _subtype='pdf')
    pdf_part.add_header(
        'Content-Disposition',
        'attachment',
        filename=f'sleep_report_{start_date}_to_{end_date}.pdf'
    )
    msg.attach(pdf_part)

    # Send email
    try:
        print(f"Sending email to: {recipient}")

        response = ses.send_raw_email(
            Source=sender,
            Destinations=[recipient],
            RawMessage={'Data': msg.as_string()}
        )

        print(f"Email sent! Message ID: {response['MessageId']}")

    except ses.exceptions.MessageRejected as e:
        print(f"Email rejected: {str(e)}")
        raise
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        raise


def lambda_handler(event, context):
    """
    Main Lambda handler triggered by EventBridge weekly schedule.

    Args:
        event: EventBridge scheduled event
        context: Lambda context

    Returns:
        Response dict with status
    """
    try:
        print("Weekly Report Orchestrator started")

        # Step 1: Calculate date range
        start_date, end_date = calculate_week_dates()
        print(f"Generating report for: {start_date} to {end_date}")

        # Step 2: Invoke AgentCore agent
        print("Invoking Health Analyzer Agent...")
        analysis = invoke_agent(start_date, end_date)
        print("Agent analysis complete")

        # Check for errors in analysis
        if 'error' in analysis:
            raise ValueError(f"Agent returned error: {analysis['error']}")

        # Step 3: Generate PDF
        print("Generating PDF report...")
        pdf_content = generate_pdf_report(analysis, start_date, end_date)
        print(f"PDF generated ({len(pdf_content)} bytes)")

        # Step 4: Get recipient email
        recipient_email = get_recipient_email()
        print(f"Recipient email: {recipient_email}")

        # Step 5: Send email with PDF
        send_email_with_pdf(recipient_email, pdf_content, start_date, end_date, analysis)

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Weekly report sent successfully',
                'start_date': start_date,
                'end_date': end_date,
                'recipient': recipient_email
            })
        }

    except Exception as e:
        print(f"Error in weekly report orchestrator: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
