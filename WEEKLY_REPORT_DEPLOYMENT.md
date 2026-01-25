# Weekly Sleep Health Report - Deployment Guide

This guide covers deploying the weekly sleep health report feature using AWS Bedrock AgentCore, Strands framework, and Claude Sonnet 4.

## Architecture Overview

```
EventBridge Schedule (Weekly, Monday 8 AM)
    ↓
Lambda: WeeklyReportOrchestrator
    ↓ invoke_agent_runtime()
AgentCore Runtime: HealthAnalyzerAgent (Strands + Claude Sonnet 4)
    ↓ MCP Protocol
Lambda: MCPServer (DynamoDB data access)
    ↓
DynamoDB (EnvReadingsTable + SleepSessionsTable)
    ↓
PDF Report → SES Email
```

## Prerequisites

### 1. Enable Claude Sonnet 4 Access in AWS Bedrock

1. Go to [AWS Bedrock Console - Model Access](https://console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess)
2. Click **"Manage model access"** or **"Request model access"**
3. Find and select **Anthropic Claude Sonnet 4**
4. Submit use case details:
   - **Use case:** "Personal health analytics and sleep pattern analysis"
   - **Description:** "Analyzing sleep quality data and environmental factors for personalized weekly insights"
5. Submit and wait for approval (usually instant)

**Model ID:** `anthropic.claude-sonnet-4-20250514-v1:0`

### 2. Verify Email in AWS SES

1. Go to [AWS SES Console](https://console.aws.amazon.com/ses/home?region=us-east-1#/verified-identities)
2. Click **"Create identity"**
3. Select **"Email address"**
4. Enter your email address
5. Click **"Create identity"**
6. Check your email and click the verification link

**Note:** In SES sandbox mode, you can only send to verified addresses. For production, request production access.

### 3. Install Required Tools

```bash
# Install AWS SAM CLI
pip install aws-sam-cli

# Install Bedrock AgentCore Starter Toolkit
pip install bedrock-agentcore-starter-toolkit

# Install Docker (for building agent container)
# Follow instructions at: https://docs.docker.com/get-docker/
```

## Deployment Steps

### Step 1: Deploy Backend Infrastructure

This deploys the MCP Server Lambda and Weekly Report Orchestrator Lambda.

```bash
cd /home/user/sleep-quality-advisor/backend

# Build the SAM application
sam build

# Deploy with parameters
sam deploy \
  --parameter-overrides \
    ReportEmailAddress="your-email@example.com" \
    AgentRuntimeArn="PLACEHOLDER"

# Note: We'll update AgentRuntimeArn after deploying the agent in Step 2
```

**Save the outputs:**
- `MCPServerFunctionUrl` - You'll need this for the agent configuration
- `MCPServerFunctionArn` - Required for agent IAM permissions

### Step 2: Deploy Health Analyzer Agent to AgentCore Runtime

#### Option A: Using AgentCore Starter Toolkit (Recommended)

```bash
cd /home/user/sleep-quality-advisor/backend/src/health_analyzer_agent

# Configure the agent for deployment
agentcore configure \
  -e agent.py \
  --protocol LAMBDA \
  --name health-analyzer-agent

# During configuration, provide:
# - Execution role: Select/create a role with Bedrock and Lambda invoke permissions
# - ECR repository: Let it auto-create or specify existing
# - Region: us-east-1

# Launch the agent to AgentCore Runtime
agentcore launch

# This will:
# 1. Build the Docker container
# 2. Push to ECR
# 3. Deploy to AgentCore Runtime
# 4. Return the Agent ARN

# Save the Agent ARN - it will look like:
# arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/health-analyzer-agent-abc123
```

#### Option B: Manual Deployment

If the toolkit doesn't work, you can deploy manually:

```bash
# 1. Create ECR repository
aws ecr create-repository \
  --repository-name sleep-health-analyzer-agent \
  --region us-east-1

# 2. Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

# 3. Build and tag the image
cd /home/user/sleep-quality-advisor/backend/src/health_analyzer_agent

docker build -t sleep-health-analyzer-agent .

docker tag sleep-health-analyzer-agent:latest \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/sleep-health-analyzer-agent:latest

# 4. Push to ECR
docker push $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/sleep-health-analyzer-agent:latest

# 5. Deploy to AgentCore Runtime (requires custom resource or AWS CLI when available)
# For now, use the agentcore toolkit method
```

### Step 3: Update CloudFormation with Agent ARN

After deploying the agent, update the CloudFormation stack with the Agent ARN:

```bash
cd /home/user/sleep-quality-advisor/backend

# Update the stack with the Agent ARN
sam deploy \
  --parameter-overrides \
    ReportEmailAddress="your-email@example.com" \
    AgentRuntimeArn="arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/health-analyzer-agent-abc123"

# Replace the ARN with your actual Agent ARN from Step 2
```

### Step 4: Configure Agent IAM Permissions

The agent needs permission to:
1. Invoke the MCP Server Lambda
2. Access Bedrock Claude Sonnet 4

Create/update the agent's execution role:

```bash
# Get the MCP Server Function ARN from CloudFormation outputs
MCP_ARN=$(aws cloudformation describe-stacks \
  --stack-name sleep-quality-advisor-backend \
  --query 'Stacks[0].Outputs[?OutputKey==`MCPServerFunctionArn`].OutputValue' \
  --output text)

# Create IAM policy document
cat > agent-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction",
        "lambda:InvokeFunctionUrl"
      ],
      "Resource": "${MCP_ARN}"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-20250514-v1:0"
    }
  ]
}
EOF

# Attach to the agent's execution role
# (Role name depends on how you deployed the agent)
aws iam put-role-policy \
  --role-name <AGENT_EXECUTION_ROLE_NAME> \
  --policy-name AgentCoreHealthAnalyzerPolicy \
  --policy-document file://agent-policy.json
```

### Step 5: Update Report Email Address

Update the SSM parameter with your verified email:

```bash
aws ssm put-parameter \
  --name /sleep-advisor/report-email \
  --value "your-verified-email@example.com" \
  --overwrite \
  --region us-east-1
```

### Step 6: Test the System

#### Manual Test

Invoke the Weekly Report Lambda manually:

```bash
aws lambda invoke \
  --function-name sleep-quality-advisor-backend-WeeklyReportFunction-XXXXX \
  --payload '{}' \
  --region us-east-1 \
  response.json

cat response.json
```

Check for:
1. ✅ Lambda execution succeeds
2. ✅ Agent invocation completes
3. ✅ PDF generated
4. ✅ Email sent

Check your email inbox for the weekly report!

#### Check CloudWatch Logs

```bash
# Get the log group name
aws logs describe-log-groups \
  --log-group-name-prefix /aws/lambda/sleep-quality-advisor-backend-WeeklyReportFunction \
  --region us-east-1

# Tail the logs
aws logs tail /aws/lambda/sleep-quality-advisor-backend-WeeklyReportFunction-XXXXX \
  --follow \
  --region us-east-1
```

## Configuration

### Change Report Schedule

Default: Every Monday at 8:00 AM UTC

To change, update the CloudFormation template (`backend/template.yaml`):

```yaml
WeeklyReportFunction:
  Events:
    WeeklySchedule:
      Type: Schedule
      Properties:
        Schedule: "cron(0 8 ? * MON *)"  # Change this cron expression
```

Cron format: `cron(minute hour day-of-month month day-of-week year)`

Examples:
- Every Monday 8 AM UTC: `cron(0 8 ? * MON *)`
- Every Sunday 9 AM UTC: `cron(0 9 ? * SUN *)`
- Every day 7 AM UTC: `cron(0 7 * * ? *)`

### Change Model

To use a different Claude model, update the agent environment variable:

```yaml
# In health_analyzer_agent/Dockerfile
ENV BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0

# Or configure via AgentCore Runtime environment variables
```

Available models:
- `anthropic.claude-sonnet-4-20250514-v1:0` - Claude Sonnet 4 (recommended)
- `anthropic.claude-3-5-sonnet-20241022-v2:0` - Claude 3.5 Sonnet v2 (if enabled)
- `anthropic.claude-3-haiku-20240307-v1:0` - Claude 3 Haiku (budget option)

## Troubleshooting

### Email Not Received

1. **Check SES email verification:**
   ```bash
   aws ses get-identity-verification-attributes \
     --identities your-email@example.com \
     --region us-east-1
   ```
   Should show `VerificationStatus: Success`

2. **Check SES sandbox mode:**
   - In sandbox mode, you can only send to verified addresses
   - Request production access if needed

3. **Check Lambda logs:**
   ```bash
   aws logs tail /aws/lambda/sleep-quality-advisor-backend-WeeklyReportFunction-XXXXX \
     --region us-east-1
   ```

### Agent Invocation Fails

1. **Verify Agent ARN is correct:**
   ```bash
   aws cloudformation describe-stacks \
     --stack-name sleep-quality-advisor-backend \
     --query 'Stacks[0].Parameters[?ParameterKey==`AgentRuntimeArn`].ParameterValue' \
     --output text
   ```

2. **Check Agent status:**
   ```bash
   # Using agentcore toolkit
   agentcore status
   ```

3. **Verify IAM permissions:**
   - Lambda needs `bedrock-agentcore:InvokeAgentRuntime`
   - Agent needs `lambda:InvokeFunctionUrl` for MCP server
   - Agent needs `bedrock:InvokeModel` for Claude Sonnet 4

### MCP Server Issues

1. **Test MCP server directly:**
   ```bash
   aws lambda invoke \
     --function-name sleep-quality-advisor-backend-MCPServerFunction-XXXXX \
     --payload '{"body": "{}"}' \
     --region us-east-1 \
     response.json
   ```

2. **Check DynamoDB data exists:**
   ```bash
   aws dynamodb scan \
     --table-name <SleepSessionsTable> \
     --max-items 1 \
     --region us-east-1
   ```

### Claude Sonnet 4 Access Denied

1. **Verify model is enabled:**
   ```bash
   aws bedrock list-foundation-models \
     --query 'modelSummaries[?contains(modelId, `claude-sonnet-4`)]' \
     --region us-east-1
   ```

2. **Re-enable model access in Bedrock console**

3. **Check IAM permissions for `bedrock:InvokeModel`**

## Cost Estimate

### Monthly Cost Breakdown

| Service | Usage | Cost/Month |
|---------|-------|------------|
| **Claude Sonnet 4** | ~9K tokens/week × 4 weeks | $0.32 |
| **AgentCore Runtime** | ~5 min runtime/week | $0.00 |
| **Lambda (WeeklyReport)** | 4 invocations × 60s | $0.00 |
| **Lambda (MCPServer)** | ~40 invocations/month | $0.00 |
| **SES** | 4 emails/month | $0.00 |
| **ECR** | 500MB image storage | $0.05 |
| **DynamoDB** | Existing data reads | $0.00 |
| **EventBridge** | 4 events/month | $0.00 |
| **Total** | | **~$0.37/month** |

**Annual:** ~$4.44

## Maintenance

### Update Agent Code

When you modify the agent code:

```bash
cd /home/user/sleep-quality-advisor/backend/src/health_analyzer_agent

# Rebuild and redeploy
agentcore launch

# Or manually rebuild container and push to ECR
```

### Monitor Performance

```bash
# Check recent report executions
aws logs tail /aws/lambda/sleep-quality-advisor-backend-WeeklyReportFunction-XXXXX \
  --since 7d \
  --region us-east-1

# Check agent metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Bedrock \
  --metric-name Invocations \
  --dimensions Name=ModelId,Value=anthropic.claude-sonnet-4-20250514-v1:0 \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum \
  --region us-east-1
```

## Security Considerations

- ✅ All data access is private (no public endpoints)
- ✅ MCP Server uses AWS IAM authentication
- ✅ Agent Runtime is isolated in AWS infrastructure
- ✅ DynamoDB data is encrypted at rest
- ✅ Email sent via SES with TLS encryption
- ✅ Secrets stored in Secrets Manager (Fitbit tokens)
- ✅ SSM Parameter for email address

## Support

If you encounter issues:

1. Check CloudWatch Logs for all Lambda functions
2. Verify all IAM permissions are correctly configured
3. Ensure Claude Sonnet 4 model access is enabled
4. Confirm email is verified in SES
5. Test each component individually (MCP Server → Agent → Report Lambda)

## Next Steps

After deployment:

1. ✅ Verify first report is received on Monday
2. ✅ Review insights for accuracy
3. ✅ Adjust system prompt if needed (in `agent.py`)
4. ✅ Monitor costs in AWS Cost Explorer
5. ✅ Consider adding more environmental sensors for richer insights

## Files Created

```
backend/
├── src/
│   ├── mcp_server/
│   │   ├── handler.py              # MCP Server Lambda
│   │   └── requirements.txt
│   ├── health_analyzer_agent/
│   │   ├── agent.py                # Strands Agent
│   │   ├── Dockerfile              # Container for AgentCore
│   │   └── requirements.txt
│   └── weekly_report/
│       ├── handler.py              # Orchestrator Lambda
│       ├── pdf_generator.py        # PDF generation
│       └── requirements.txt
└── template.yaml                   # Updated CloudFormation
```

---

**Deployment Complete!** 🎉

Your weekly sleep health report system is now deployed and will automatically generate reports every Monday at 8 AM UTC.
