# Dockerfile for Health Analyzer Agent (Strands + AgentCore Runtime)
# This container will be deployed to AWS Bedrock AgentCore Runtime

FROM public.ecr.aws/lambda/python:3.12

# Set working directory
WORKDIR /var/task

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy agent code
COPY agent.py .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0
ENV AWS_REGION=us-east-1

# For AgentCore Runtime, we need to expose port 8000
EXPOSE 8000

# Entry point for the agent
# AgentCore Runtime will invoke this handler
CMD ["agent.handler"]
