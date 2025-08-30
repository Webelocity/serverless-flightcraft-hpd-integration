# HPD Pricing Integration - Serverless (SAM)

This project has been migrated from FastAPI to AWS Serverless using SAM (Serverless Application Model).

## Architecture

- **API Gateway + Lambda Functions** for HTTP endpoints (replacing FastAPI)
- **EventBridge Scheduler** for cron jobs (replacing APScheduler)
- **S3** for file storage (cost-effective for large JSON files)
- **Lambda Layers** for shared dependencies
- **CloudFormation** for infrastructure as code

## Functions

| Original FastAPI Endpoint | Lambda Function        | Description               |
| ------------------------- | ---------------------- | ------------------------- |
| `GET /health`             | `HealthFunction`       | Health check              |
| `POST /run-now`           | `RunNowFunction`       | Manual job trigger        |
| `POST /test-email`        | `TestEmailFunction`    | Test email functionality  |
| `GET /status`             | `StatusFunction`       | Check scheduler status    |
| Scheduled Job             | `ScheduledJobFunction` | EventBridge triggered job |

## Prerequisites

1. **AWS CLI** installed and configured
2. **SAM CLI** installed ([Installation Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
3. **Python 3.11** installed
4. **Docker** installed (for SAM build)

## Setup

1. **Copy environment template:**

   ```bash
   cp .env.template .env
   ```

2. **Fill in your environment variables in `.env` file:**
   - HPD API credentials
   - SMTP email configuration
   - Toolswift API credentials

## Deployment

### Option 1: Using PowerShell (Windows)

```powershell
.\deploy.ps1
```

### Option 2: Using Bash (Linux/Mac/WSL)

```bash
chmod +x deploy.sh
./deploy.sh
```

### Option 3: Manual deployment

```bash
# Build the application
sam build

# Deploy with guided setup (first time)
sam deploy --guided

# Deploy with existing configuration
sam deploy
```

## Configuration Parameters

During deployment, you'll be prompted for:

- **Stack Name**: Name for your CloudFormation stack
- **AWS Region**: Where to deploy (e.g., us-east-1)
- **HPD API Credentials**: Your HPD API ID and Key
- **Email Configuration**: SMTP settings for notifications
- **Toolswift Configuration**: Your Toolswift API credentials
- **Schedule Expression**: Cron or rate expression for scheduling

### Schedule Expression Examples

- `rate(60 minutes)` - Every hour
- `rate(1 day)` - Every day
- `cron(0 9 * * ? *)` - Every day at 9:00 AM UTC
- `cron(0 */2 * * ? *)` - Every 2 hours

## Testing

After deployment, you'll get an API Gateway endpoint URL. Test the endpoints:

```bash
# Health check
curl https://your-api-id.execute-api.region.amazonaws.com/prod/health

# Manual job trigger
curl -X POST https://your-api-id.execute-api.region.amazonaws.com/prod/run-now

# Test email
curl -X POST "https://your-api-id.execute-api.region.amazonaws.com/prod/test-email?to=test@example.com"

# Check status
curl https://your-api-id.execute-api.region.amazonaws.com/prod/status
```

## Monitoring

- **CloudWatch Logs**: Each Lambda function creates its own log group
- **CloudWatch Metrics**: Monitor invocation count, duration, errors
- **X-Ray Tracing**: Enable in template.yaml for detailed tracing

## Cost Optimization

- **Lambda**: Pay per invocation and duration
- **S3**: Cost-effective storage for large JSON files with lifecycle policies
- **EventBridge**: Minimal cost for scheduled events
- **API Gateway**: Pay per API call

Estimated monthly cost for typical usage: $5-20 (much lower than running EC2/containers)

## Differences from FastAPI Version

| Aspect           | FastAPI Version                | SAM Version               |
| ---------------- | ------------------------------ | ------------------------- |
| **Runtime**      | Always-on server               | Event-driven functions    |
| **Scheduling**   | APScheduler (in-process)       | EventBridge (managed)     |
| **File Storage** | Local filesystem               | S3 (persistent, scalable) |
| **Scaling**      | Manual/container orchestration | Automatic                 |
| **Cost**         | Fixed (server running 24/7)    | Variable (pay per use)    |
| **Dependencies** | All loaded at startup          | Shared via Lambda Layers  |

## Migration Notes

1. **File Storage**: Large JSON files now stored in S3 instead of local filesystem
2. **Scheduling**: EventBridge replaces APScheduler for better reliability
3. **Environment**: Each function runs independently with shared dependencies
4. **Configuration**: Parameters passed via CloudFormation instead of environment files
5. **Monitoring**: Native AWS monitoring instead of custom logging

## Troubleshooting

### Common Issues

1. **Build Failures**:
   - Ensure Docker is running
   - Check Python version (3.11 required)

2. **Deployment Failures**:
   - Verify AWS CLI configuration
   - Check IAM permissions
   - Ensure unique S3 bucket name

3. **Function Errors**:
   - Check CloudWatch logs
   - Verify environment variables
   - Test API credentials

### Rollback

If you need to rollback:

```bash
aws cloudformation delete-stack --stack-name your-stack-name
```

## Development

### Local Testing

```bash
# Start API locally
sam local start-api --port 8000

# Test individual functions
sam local invoke HealthFunction
sam local invoke RunNowFunction
```

### Updating

After making changes:

```bash
sam build
sam deploy
```
