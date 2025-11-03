# Setup Guide - Getting Started with ModelGuard

Complete setup guide for local development and deployment.

## Prerequisites

1. **Python 3.12** (matches Lambda runtime)
2. **AWS CLI** installed and configured
   ```bash
   aws configure
   ```
3. **Docker Desktop** installed and running
4. **AWS SAM CLI** installed
   ```bash
   # Windows (using chocolatey)
   choco install aws-sam-cli
   
   # Or download from: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
   ```

## Local Development Setup

### 1. Install Dependencies

```powershell
# Create virtual environment (optional but recommended)
py -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 2. Local Testing with SAM (Docker)

SAM uses Docker to simulate Lambda functions locally.

#### Start Local API Server

```powershell
# Build and start local API
sam build
sam local start-api

# This will start API Gateway on http://127.0.0.1:3000
```

#### Test Endpoints Locally

Once the local API is running:

```powershell
# Test POST upload
$testFile = "Test model content"
$testFile | Out-File -FilePath test.txt -Encoding utf8

curl.exe -X POST "http://127.0.0.1:3000/artifact/model" `
  -H "Content-Type: application/octet-stream" `
  -H "X-Model-Name: test-model" `
  --data-binary "@test.txt"

# Test GET download
curl.exe "http://127.0.0.1:3000/artifacts/model/test-model?metadata_only=true"
```

### 3. Environment Variables

Environment variables are defined in `template.yaml`:

- `ARTIFACTS_TABLE`: DynamoDB table name (auto-set by SAM)
- `ARTIFACTS_BUCKET`: S3 bucket name (auto-set by SAM)
- `LOG_LEVEL`: Set to `DEBUG` for verbose logging
- `API_BASE`: API Gateway URL (for web app)

For local testing, SAM automatically provides these values.

### 4. Frontend Setup

The React frontend is in `web/` directory (FastAPI app via Mangum).

#### Local Frontend Development

```powershell
cd web

# If using npm/yarn
npm install
npm run dev

# The frontend expects API_BASE environment variable
# In production, this is set by template.yaml
# For local dev, you may need to set it manually:
$env:API_BASE = "http://127.0.0.1:3000"
```

#### Frontend Configuration

The frontend uses `API_BASE` from environment:
- **Production**: Set in `template.yaml` as API Gateway URL
- **Local Dev**: Points to `sam local start-api` endpoint (http://127.0.0.1:3000)

## Deployment to AWS

### 1. Build and Deploy with SAM

```powershell
# Build the application
sam build

# Deploy (first time - guided setup)
sam deploy --guided

# Subsequent deployments
sam deploy
```

This will:
- Create S3 bucket (`modelguard-artifacts-files`)
- Create DynamoDB table (`ModelGuard-Artifacts-Metadata`)
- Deploy all Lambda functions
- Create API Gateway
- Set environment variables automatically

### 2. Get Your API Gateway URL

After deployment, SAM outputs the API Gateway URL:

```
ModelGuardApi:
  ApiGatewayUrl: https://XXXXXXXXXX.execute-api.us-east-1.amazonaws.com/dev/
```

Use this URL for:
- Testing endpoints
- Frontend `API_BASE` configuration
- Autograder submission

### 3. Update Frontend API URL

The frontend is hosted on AWS Amplify (Ryan set this up). The `API_BASE` environment variable should point to your deployed API Gateway URL.

## Testing

### Run Unit Tests

```powershell
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_model.py
```

### Test Lambda Functions Locally

You can invoke Lambda functions directly with SAM:

```powershell
# Test POST upload function
sam local invoke PostArtifactUploadFunction -e test-event.json

# Test GET download function  
sam local invoke GetArtifactDownloadFunction -e test-event.json
```

### Create Test Event

Create `test-event.json`:

```json
{
  "httpMethod": "POST",
  "path": "/artifact/model",
  "pathParameters": {
    "artifact_type": "model"
  },
  "headers": {
    "Content-Type": "application/octet-stream",
    "X-Model-Name": "test-model"
  },
  "body": "base64-encoded-content-here",
  "isBase64Encoded": true
}
```

## Troubleshooting

### SAM Local Issues

- **Docker not running**: Make sure Docker Desktop is running
- **Port already in use**: Change port with `sam local start-api --port 3001`
- **Timeout errors**: Increase timeout in `template.yaml` or check Docker resources

### AWS Deployment Issues

- **Permission errors**: Check IAM role in `template.yaml` (BasicLambdaRole)
- **Bucket already exists**: S3 bucket names must be globally unique
- **Table creation failed**: Check DynamoDB service quotas

### Import Errors

If you get import errors locally:

```powershell
# Make sure PYTHONPATH is set
$env:PYTHONPATH = "$PWD;$PWD/src"

# Or use the same PYTHONPATH as Lambda (defined in template.yaml)
```

## Project Structure

```
.
├── lambdas/          # Individual Lambda function handlers
│   ├── post_artifact_upload.py
│   ├── get_artifact_download.py
│   └── ...
├── src/              # Shared source code
│   ├── model.py     # Model class
│   └── metrics/     # Metric implementations
├── web/              # Frontend (FastAPI/React)
│   ├── app.py       # FastAPI app (Mangum handler)
│   └── ...
├── template.yaml     # SAM template (infrastructure as code)
├── requirements.txt  # Python dependencies
└── README.md         # Project overview
```

## Quick Start Checklist

- [ ] Install Python 3.12
- [ ] Install AWS CLI and configure credentials
- [ ] Install Docker Desktop
- [ ] Install AWS SAM CLI
- [ ] Clone repository and install dependencies
- [ ] Test locally: `sam build && sam local start-api`
- [ ] Deploy to AWS: `sam deploy --guided`
- [ ] Get API Gateway URL from deployment output
- [ ] Test endpoints with curl or Postman

## Next Steps

1. **Authentication**: Set up Cognito (Ryan mentioned this)
2. **Testing**: Add integration tests for Lambda functions
3. **CI/CD**: GitHub Actions for automated deployment (already configured)
4. **Monitoring**: Set up CloudWatch alarms and dashboards

## Useful Commands

```powershell
# SAM commands
sam build                    # Build application
sam local start-api          # Start local API Gateway
sam local invoke <function>  # Invoke single function
sam deploy                   # Deploy to AWS
sam logs -n <function>       # View Lambda logs

# Testing
pytest                       # Run all tests
pytest -v                    # Verbose output
pytest tests/test_model.py   # Run specific test

# Git
git status                   # Check changes
git add .                    # Stage changes
git commit -m "message"      # Commit
git push                     # Push to remote
```

## Resources

- **AWS SAM Documentation**: https://docs.aws.amazon.com/serverless-application-model/
- **Local Testing Guide**: Check "Misc/Local Testing" in Loop (Ryan's doc)
- **API Gateway URLs**: Found in SAM deployment output or AWS Console

