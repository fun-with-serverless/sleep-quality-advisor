# IAM Permissions Guide for Sleep Quality Advisor Deployment

This document explains the minimal IAM permissions required to deploy both the backend and Streamlit stacks.

## Quick Start

The IAM policy is available in `iam-deployment-policy.json`. You can create an IAM user or role with this policy attached.

### Option 1: Create IAM User (Recommended for Manual Deployments)

```bash
# Create IAM user
aws iam create-user --user-name sleep-quality-advisor-deployer

# Create policy
aws iam create-policy \
  --policy-name SleepQualityAdvisorDeploymentPolicy \
  --policy-document file://iam-deployment-policy.json

# Attach policy to user (replace ACCOUNT_ID with your AWS account ID)
aws iam attach-user-policy \
  --user-name sleep-quality-advisor-deployer \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/SleepQualityAdvisorDeploymentPolicy

# Create access keys
aws iam create-access-key --user-name sleep-quality-advisor-deployer
```

### Option 2: Create IAM Role (Recommended for CI/CD)

```bash
# Create trust policy for EC2 or your CI/CD service
cat > trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name SleepQualityAdvisorDeploymentRole \
  --assume-role-policy-document file://trust-policy.json

# Create and attach policy
aws iam create-policy \
  --policy-name SleepQualityAdvisorDeploymentPolicy \
  --policy-document file://iam-deployment-policy.json

aws iam attach-role-policy \
  --role-name SleepQualityAdvisorDeploymentRole \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/SleepQualityAdvisorDeploymentPolicy
```

## Permission Breakdown

### Core Services (Required for Both Stacks)

#### CloudFormation (Full Access)
- **Why**: SAM deployments use CloudFormation to create, update, and delete infrastructure
- **Actions**: Create/update/delete stacks, change sets, describe resources, list exports
- **Scope**: All stacks

#### S3 (Deployment Artifacts)
- **Why**: SAM packages Lambda code and stores it in S3
- **Actions**: Create bucket, put/get objects, manage lifecycle
- **Scope**: Only `aws-sam-cli-managed-default-*` buckets

#### IAM (Role Management)
- **Why**: Create execution roles for Lambda, ECS tasks, etc.
- **Actions**: Create/delete roles, attach/detach policies, pass role
- **Scope**: Roles with prefix `sleep-quality-advisor-*` and `streamlit-*`

### Backend Stack Services

#### Lambda Functions
- **Why**: Serverless functions for API endpoints and scheduled tasks
- **Actions**: Create/delete/update functions, event source mappings, permissions
- **Scope**: Functions with prefix `sleep-quality-advisor-*`

#### API Gateway
- **Why**: REST API for data ingestion and Fitbit OAuth
- **Actions**: Create/update/delete REST APIs and resources
- **Scope**: All REST APIs in the region

#### DynamoDB
- **Why**: Store environmental readings and sleep sessions
- **Actions**: Create/delete/update tables, manage backups, tagging
- **Scope**: All tables

#### SQS
- **Why**: Queue for asynchronous processing of environmental data
- **Actions**: Create/delete queues, manage attributes
- **Scope**: All queues

#### Secrets Manager
- **Why**: Store API keys, OAuth tokens, and shared secrets
- **Actions**: Create/delete/update secrets, get secret values
- **Scope**: Secrets under `ingest/*`, `fitbit/*`, and `streamlit/*`

#### SSM Parameter Store
- **Why**: Store Fitbit client ID
- **Actions**: Put/get/delete parameters
- **Scope**: Parameters under `/fitbit/*`

#### EventBridge (CloudWatch Events)
- **Why**: Schedule daily Fitbit data fetch
- **Actions**: Create/delete rules, put/remove targets
- **Scope**: All rules

#### CloudWatch Logs
- **Why**: Lambda function logs
- **Actions**: Create/delete log groups, set retention
- **Scope**: All log groups

#### X-Ray
- **Why**: Distributed tracing for Lambda functions
- **Actions**: Put trace segments
- **Scope**: All resources

### Streamlit Stack Services

#### ECR (Container Registry)
- **Why**: Store Docker images for Streamlit app
- **Actions**: Create repositories, push/pull images, manage lifecycle policies
- **Scope**: Repositories with prefix `sleep-quality-advisor-*`

#### ECS (Container Orchestration)
- **Why**: Run Streamlit app as containerized service
- **Actions**: Create clusters, services, task definitions
- **Scope**: All ECS resources

#### ECS Express Gateway
- **Why**: Simplified container deployment with built-in ALB
- **Actions**: Create/update/delete Express Gateway services
- **Scope**: All resources

#### VPC & Networking (EC2)
- **Why**: ECS Express automatically creates VPC, subnets, security groups
- **Actions**: Create/manage VPCs, subnets, route tables, security groups, internet gateways
- **Scope**: All VPC resources

#### Elastic Load Balancing
- **Why**: ECS Express creates ALB with SSL/TLS
- **Actions**: Create/manage ALBs, target groups, listeners
- **Scope**: All load balancers

#### ACM (Certificate Manager)
- **Why**: ECS Express creates SSL/TLS certificates
- **Actions**: Request/delete certificates
- **Scope**: All certificates

#### STS (Security Token Service)
- **Why**: Used by taskipy scripts to get AWS account ID
- **Actions**: GetCallerIdentity
- **Scope**: All resources

## Security Considerations

### Principle of Least Privilege

The policy follows least privilege principles:

1. **Scoped Resources**: Where possible, permissions are limited to specific resource patterns (e.g., `sleep-quality-advisor-*`)
2. **No Write Access to Data**: Deployment user cannot read/write DynamoDB data or secrets content
3. **No Production Access**: Deployment permissions are separate from runtime permissions
4. **Limited IAM Actions**: Can only create roles with specific name patterns

### Resource Boundaries

Some resources use wildcards (`*`) because:
- CloudFormation requires broad describe permissions
- ECS Express dynamically creates VPC resources with unpredictable names
- ECR GetAuthorizationToken works at account level

### Recommended Security Enhancements

1. **Condition Keys**: Add condition keys to limit deployments to specific regions:
   ```json
   "Condition": {
     "StringEquals": {
       "aws:RequestedRegion": "us-east-1"
     }
   }
   ```

2. **MFA Required**: Require MFA for deployment user:
   ```json
   "Condition": {
     "BoolIfExists": {
       "aws:MultiFactorAuthPresent": "true"
     }
   }
   ```

3. **IP Restrictions**: Limit deployments to specific IP ranges:
   ```json
   "Condition": {
     "IpAddress": {
       "aws:SourceIp": ["YOUR_IP_RANGE"]
     }
   }
   ```

## Cost Impact

These permissions allow creation of resources that incur costs:

- **Backend**: ~$5-10/month (Lambda, DynamoDB on-demand, API Gateway)
- **Streamlit**: ~$33-35/month (ECS Fargate, ALB)
- **Storage**: <$1/month (S3, ECR, CloudWatch Logs)

Consider setting up AWS Budgets to monitor spending:

```bash
aws budgets create-budget \
  --account-id ACCOUNT_ID \
  --budget file://budget.json \
  --notifications-with-subscribers file://notifications.json
```

## Testing the Policy

Before deploying to production, test in a sandbox account:

1. Create test IAM user with the policy
2. Attempt backend deployment: `cd backend && uv run task deploy`
3. Attempt streamlit deployment: `cd streamlit && uv run task deploy-infra`
4. Verify all resources are created successfully
5. Clean up: Delete both stacks

## Troubleshooting

### "User is not authorized to perform X"

If you encounter authorization errors:

1. Check the error message for the specific action and resource
2. Verify the resource name matches the policy patterns
3. Check if the action is included in the policy
4. Review CloudTrail logs for denied API calls

### Common Issues

- **IAM PassRole errors**: Ensure IAM:PassRole is included for role ARNs
- **S3 bucket errors**: Bucket names must match `aws-sam-cli-managed-default-*`
- **ECR push errors**: Ensure ECR GetAuthorizationToken is allowed
- **Cross-stack reference errors**: Ensure CloudFormation ListExports is allowed

## Revoking Access

To remove deployment permissions:

```bash
# Detach policy
aws iam detach-user-policy \
  --user-name sleep-quality-advisor-deployer \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/SleepQualityAdvisorDeploymentPolicy

# Delete policy
aws iam delete-policy \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/SleepQualityAdvisorDeploymentPolicy

# Delete user (optional)
aws iam delete-user --user-name sleep-quality-advisor-deployer
```

## Support

If you need to modify the policy for your specific use case:

1. Deploy in a test environment first
2. Review CloudTrail logs for any denied actions
3. Add only the specific actions that failed
4. Test again before applying to production
