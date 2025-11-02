# Quick Start: Deploy to AWS

Fastest way to get your Lambda handler running on AWS.

## Prerequisites Check

```bash
# Check AWS CLI is installed and configured
aws --version
aws sts get-caller-identity  # Should show your account info

# Check Python is available
py --version  # or python3 --version
```

## Option 1: Automated Script (Linux/Mac/Git Bash)

```bash
# Make script executable
chmod +x deploy.sh

# Edit deploy.sh to set your bucket name, then run:
./deploy.sh
```

## Option 2: Manual Steps (Windows PowerShell)

### 1. Set Variables

```powershell
$BUCKET_NAME = "modelguard-artifacts-$(Get-Random)"
$TABLE_NAME = "ModelGuard-Models"
$REGION = "us-east-1"
$FUNCTION_NAME = "ModelGuard-ArtifactHandler"
```

### 2. Create S3 Bucket

```powershell
aws s3 mb s3://$BUCKET_NAME --region $REGION
```

### 3. Create DynamoDB Table

```powershell
aws dynamodb create-table `
  --table-name $TABLE_NAME `
  --attribute-definitions AttributeName=name,AttributeType=S `
  --key-schema AttributeName=name,KeyType=HASH `
  --billing-mode PAY_PER_REQUEST `
  --region $REGION
```

### 4. Create IAM Role

Save this as `trust-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
```

```powershell
# Create role
aws iam create-role `
  --role-name ModelGuard-LambdaRole `
  --assume-role-policy-document file://trust-policy.json

# Get role ARN
$ROLE_ARN = (aws iam get-role --role-name ModelGuard-LambdaRole --query 'Role.Arn' --output text)

# Create policy (save as lambda-policy.json, replace BUCKET_NAME)
aws iam put-role-policy `
  --role-name ModelGuard-LambdaRole `
  --policy-name ModelGuard-LambdaPolicy `
  --policy-document file://lambda-policy.json
```

Create `lambda-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"],
      "Resource": "arn:aws:dynamodb:*:*:table/ModelGuard-Models"
    }
  ]
}
```

### 5. Package Lambda

```powershell
# Create package directory
New-Item -ItemType Directory -Path lambda-package -Force

# Copy source
Copy-Item -Recurse -Path src -Destination lambda-package\

# Install dependencies
pip install -r requirements.txt -t lambda-package\

# Create zip (requires 7-Zip or PowerShell 5.0+)
Compress-Archive -Path lambda-package\* -DestinationPath lambda-deployment.zip
```

### 6. Deploy Lambda

```powershell
aws lambda create-function `
  --function-name $FUNCTION_NAME `
  --runtime python3.11 `
  --role $ROLE_ARN `
  --handler src.lambda_handlers.lambda_handler `
  --zip-file fileb://lambda-deployment.zip `
  --timeout 30 `
  --memory-size 256 `
  --environment Variables="{S3_BUCKET=$BUCKET_NAME,DYNAMODB_TABLE=$TABLE_NAME,AWS_REGION=$REGION}"
```

### 7. Create API Gateway (Simplified)

For a complete setup, see `AWS_DEPLOYMENT_GUIDE.md`. Quick version:

```powershell
# Create API
$API_ID = (aws apigateway create-rest-api --name ModelGuard-API --query 'id' --output text)

# Get root resource
$ROOT_ID = (aws apigateway get-resources --rest-api-id $API_ID --query 'items[?path==`/`].id' --output text)

# Create resources and methods (see AWS_DEPLOYMENT_GUIDE.md for full steps)

# Deploy
aws apigateway create-deployment --rest-api-id $API_ID --stage-name prod

# Get endpoint
$ENDPOINT = "https://${API_ID}.execute-api.${REGION}.amazonaws.com/prod"
echo $ENDPOINT
```

## Option 3: Use AWS Console (GUI)

1. **S3 Console**: Create bucket manually
2. **DynamoDB Console**: Create table with `name` as primary key
3. **IAM Console**: Create role with Lambda trust policy and permissions
4. **Lambda Console**: 
   - Create function → Upload zip file
   - Set handler: `src.lambda_handlers.lambda_handler`
   - Set environment variables
5. **API Gateway Console**: Create REST API and connect to Lambda

## Testing After Deployment

```powershell
# Set your API endpoint
$ENDPOINT = "https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod"

# Test upload
$testFile = "Test content"
$testFile | Out-File -FilePath test.txt -Encoding utf8
curl.exe -X POST "$ENDPOINT/artifact/model" `
  -H "Content-Type: application/octet-stream" `
  -H "X-Model-Name: test-model" `
  --data-binary "@test.txt"

# Test download
curl.exe "$ENDPOINT/artifacts/model/test-model?metadata_only=true"
```

## Troubleshooting

### Check Lambda Logs

```powershell
aws logs tail /aws/lambda/ModelGuard-ArtifactHandler --follow
```

### Update Lambda Code

After making changes:

```powershell
# Re-package
Compress-Archive -Path lambda-package\* -DestinationPath lambda-deployment.zip -Force

# Update function
aws lambda update-function-code `
  --function-name ModelGuard-ArtifactHandler `
  --zip-file fileb://lambda-deployment.zip
```

### Common Errors

- **Access Denied**: Check IAM role permissions
- **Function Not Found**: Wait a few seconds after creation
- **Timeout**: Increase timeout in Lambda settings
- **S3 Error**: Verify bucket name in environment variables

## Next Steps

1. Complete API Gateway setup (see `AWS_DEPLOYMENT_GUIDE.md`)
2. Add authentication (API Keys, Cognito)
3. Set up CloudWatch alarms
4. Configure custom domain

