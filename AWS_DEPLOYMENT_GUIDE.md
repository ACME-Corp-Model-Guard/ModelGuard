# AWS Deployment Guide

Complete guide to deploy the Lambda handler to AWS and wire it up with API Gateway.

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
   ```bash
   aws --version
   aws configure  # Set up credentials and region
   ```
3. **Python 3.11** (for Lambda runtime)
4. **boto3** installed locally (already in requirements.txt)

## Step 1: Create S3 Bucket

Create an S3 bucket to store artifacts:

```bash
# Set your bucket name (must be globally unique)
BUCKET_NAME="modelguard-artifacts-your-unique-name"

# Create the bucket
aws s3 mb s3://$BUCKET_NAME

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket $BUCKET_NAME \
  --versioning-configuration Status=Enabled

# Set bucket policy for Lambda access (optional - IAM role will handle this)
aws s3api get-bucket-location --bucket $BUCKET_NAME
```

## Step 2: Create DynamoDB Table

Create a DynamoDB table for model metadata:

```bash
TABLE_NAME="ModelGuard-Models"

aws dynamodb create-table \
  --table-name $TABLE_NAME \
  --attribute-definitions AttributeName=name,AttributeType=S \
  --key-schema AttributeName=name,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1

# Wait for table to be active (check status)
aws dynamodb describe-table --table-name $TABLE_NAME --query 'Table.TableStatus'
```

**Table Structure:**
- **Primary Key**: `name` (String) - Model name
- **Attributes**: 
  - `size` (Number)
  - `license` (String)
  - `model_key`, `code_key`, `dataset_key` (String)
  - `parent_model_key` (String, optional)
  - `scores`, `scores_latency` (String - JSON)

## Step 3: Create IAM Role for Lambda

Create an IAM role with permissions for S3 and DynamoDB:

```bash
# Create trust policy file
cat > lambda-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the role
aws iam create-role \
  --role-name ModelGuard-LambdaRole \
  --assume-role-policy-document file://lambda-trust-policy.json

# Create policy file for Lambda permissions
cat > lambda-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/${TABLE_NAME}"
    }
  ]
}
EOF

# Attach policy to role
aws iam put-role-policy \
  --role-name ModelGuard-LambdaRole \
  --policy-name ModelGuard-LambdaPolicy \
  --policy-document file://lambda-policy.json

# Get the role ARN (needed for Lambda creation)
LAMBDA_ROLE_ARN=$(aws iam get-role --role-name ModelGuard-LambdaRole --query 'Role.Arn' --output text)
echo "Lambda Role ARN: $LAMBDA_ROLE_ARN"
```

## Step 4: Package Lambda Function

Package your Lambda function code:

```bash
# Create deployment package directory
mkdir -p lambda-package

# Copy source code
cp -r src lambda-package/

# Install dependencies
pip install -r requirements.txt -t lambda-package/

# Create zip file
cd lambda-package
zip -r ../lambda-deployment.zip .
cd ..

# Verify the zip file
ls -lh lambda-deployment.zip
```

**Note**: On Windows PowerShell, use:
```powershell
# Create deployment package
New-Item -ItemType Directory -Path lambda-package -Force
Copy-Item -Recurse -Path src -Destination lambda-package\
pip install -r requirements.txt -t lambda-package\

# Create zip (requires 7-Zip or similar)
Compress-Archive -Path lambda-package\* -DestinationPath lambda-deployment.zip
```

## Step 5: Create Lambda Function

Deploy the Lambda function:

```bash
# Create the Lambda function
aws lambda create-function \
  --function-name ModelGuard-ArtifactHandler \
  --runtime python3.11 \
  --role $LAMBDA_ROLE_ARN \
  --handler src.lambda_handlers.lambda_handler \
  --zip-file fileb://lambda-deployment.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment Variables="{
    S3_BUCKET=${BUCKET_NAME},
    DYNAMODB_TABLE=${TABLE_NAME},
    AWS_REGION=us-east-1
  }"

# Verify function was created
aws lambda get-function --function-name ModelGuard-ArtifactHandler
```

## Step 6: Create API Gateway REST API

Create and configure API Gateway:

```bash
# Create REST API
API_ID=$(aws apigateway create-rest-api \
  --name ModelGuard-API \
  --description "ModelGuard artifact management API" \
  --query 'id' --output text)

echo "API ID: $API_ID"

# Get root resource ID
ROOT_RESOURCE_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --query 'items[?path==`/`].id' --output text)

echo "Root Resource ID: $ROOT_RESOURCE_ID"
```

## Step 7: Create API Gateway Resources

### Create POST Resource: `/artifact/{artifact_type}`

```bash
# Create artifact resource
ARTIFACT_RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_RESOURCE_ID \
  --path-part artifact \
  --query 'id' --output text)

echo "Artifact Resource ID: $ARTIFACT_RESOURCE_ID"

# Create {artifact_type} resource
ARTIFACT_TYPE_RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ARTIFACT_RESOURCE_ID \
  --path-part {artifact_type} \
  --query 'id' --output text)

echo "Artifact Type Resource ID: $ARTIFACT_TYPE_RESOURCE_ID"

# Create POST method
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $ARTIFACT_TYPE_RESOURCE_ID \
  --http-method POST \
  --authorization-type NONE

# Set up Lambda integration
LAMBDA_ARN=$(aws lambda get-function \
  --function-name ModelGuard-ArtifactHandler \
  --query 'Configuration.FunctionArn' --output text)

aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $ARTIFACT_TYPE_RESOURCE_ID \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations

# Grant API Gateway permission to invoke Lambda
aws lambda add-permission \
  --function-name ModelGuard-ArtifactHandler \
  --statement-id apigateway-invoke-post \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:*:${API_ID}/*/*"
```

### Create GET Resource: `/artifacts/{artifact_type}/{id}`

```bash
# Create artifacts resource (note: plural)
ARTIFACTS_RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_RESOURCE_ID \
  --path-part artifacts \
  --query 'id' --output text)

# Create {artifact_type} resource
ARTIFACTS_TYPE_RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ARTIFACTS_RESOURCE_ID \
  --path-part {artifact_type} \
  --query 'id' --output text)

# Create {id} resource
ARTIFACTS_ID_RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ARTIFACTS_TYPE_RESOURCE_ID \
  --path-part {id} \
  --query 'id' --output text)

# Create GET method
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $ARTIFACTS_ID_RESOURCE_ID \
  --http-method GET \
  --authorization-type NONE

# Set up Lambda integration
aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $ARTIFACTS_ID_RESOURCE_ID \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/${LAMBDA_ARN}/invocations

# Grant API Gateway permission to invoke Lambda (for GET)
aws lambda add-permission \
  --function-name ModelGuard-ArtifactHandler \
  --statement-id apigateway-invoke-get \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:*:${API_ID}/*/*"
```

## Step 8: Enable CORS (Optional but Recommended)

```bash
# Enable CORS for POST method
aws apigateway put-method-response \
  --rest-api-id $API_ID \
  --resource-id $ARTIFACT_TYPE_RESOURCE_ID \
  --http-method POST \
  --status-code 200 \
  --response-parameters method.response.header.Access-Control-Allow-Origin=true

aws apigateway put-integration-response \
  --rest-api-id $API_ID \
  --resource-id $ARTIFACT_TYPE_RESOURCE_ID \
  --http-method POST \
  --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Origin":"'"'"'*'"'"'"}'

# Enable CORS for GET method
aws apigateway put-method-response \
  --rest-api-id $API_ID \
  --resource-id $ARTIFACTS_ID_RESOURCE_ID \
  --http-method GET \
  --status-code 200 \
  --response-parameters method.response.header.Access-Control-Allow-Origin=true

aws apigateway put-integration-response \
  --rest-api-id $API_ID \
  --resource-id $ARTIFACTS_ID_RESOURCE_ID \
  --http-method GET \
  --status-code 200 \
  --response-parameters '{"method.response.header.Access-Control-Allow-Origin":"'"'"'*'"'"'"}'
```

## Step 9: Deploy API

Deploy the API to a stage:

```bash
# Create deployment
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name prod \
  --description "Production deployment"

# Get the API endpoint URL
API_ENDPOINT="https://${API_ID}.execute-api.us-east-1.amazonaws.com/prod"
echo "API Endpoint: $API_ENDPOINT"
```

## Step 10: Test the Deployment

### Test Upload (POST)

```bash
# Create a test file
echo "Test model content" > test-model.txt

# Upload model artifact
curl -X POST \
  "${API_ENDPOINT}/artifact/model" \
  -H "Content-Type: application/octet-stream" \
  -H "X-Model-Name: test-model" \
  --data-binary "@test-model.txt"

# Or with multipart/form-data (if you have a tool that supports it)
```

### Test Download (GET)

```bash
# Get model artifact metadata
curl "${API_ENDPOINT}/artifacts/model/test-model?metadata_only=true"

# Download model artifact
curl "${API_ENDPOINT}/artifacts/model/test-model" -o downloaded-model.txt
```

## Troubleshooting

### View Lambda Logs

```bash
# View recent logs
aws logs tail /aws/lambda/ModelGuard-ArtifactHandler --follow

# Or check CloudWatch Logs in AWS Console
```

### Update Lambda Function Code

```bash
# After making code changes, update the deployment package and redeploy
cd lambda-package
# ... make changes ...
zip -r ../lambda-deployment.zip .
cd ..

aws lambda update-function-code \
  --function-name ModelGuard-ArtifactHandler \
  --zip-file fileb://lambda-deployment.zip
```

### Update Environment Variables

```bash
aws lambda update-function-configuration \
  --function-name ModelGuard-ArtifactHandler \
  --environment Variables="{
    S3_BUCKET=${BUCKET_NAME},
    DYNAMODB_TABLE=${TABLE_NAME},
    AWS_REGION=us-east-1
  }"
```

### Common Issues

1. **403 Forbidden**: Check IAM permissions for Lambda role
2. **500 Internal Server Error**: Check CloudWatch Logs for Lambda errors
3. **Timeout**: Increase Lambda timeout or optimize code
4. **S3 Access Denied**: Verify bucket name and IAM permissions

## Alternative: Use AWS SAM or CDK

For easier deployment, consider using:
- **AWS SAM (Serverless Application Model)**: Template-based deployment
- **AWS CDK (Cloud Development Kit)**: Infrastructure as code in Python

## Next Steps

1. Set up CloudWatch alarms for errors
2. Add API Gateway throttling/rate limiting
3. Set up authentication (API Keys, Cognito)
4. Enable API Gateway request/response logging
5. Configure custom domain name for API

## Quick Reference Commands

```bash
# Variables (set these first!)
export BUCKET_NAME="modelguard-artifacts-your-name"
export TABLE_NAME="ModelGuard-Models"
export REGION="us-east-1"

# Test endpoints
export API_ENDPOINT="https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod"

# View Lambda logs
aws logs tail /aws/lambda/ModelGuard-ArtifactHandler --follow

# List Lambda functions
aws lambda list-functions

# Get API Gateway details
aws apigateway get-rest-apis
```

