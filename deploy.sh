#!/bin/bash
# Quick deployment script for ModelGuard Lambda handler
# Make sure to set your variables first!

set -e  # Exit on error

# Configuration - CHANGE THESE!
BUCKET_NAME="modelguard-artifacts-$(whoami)-$(date +%s)"
TABLE_NAME="ModelGuard-Models"
REGION="us-east-1"
FUNCTION_NAME="ModelGuard-ArtifactHandler"
API_NAME="ModelGuard-API"

echo "=========================================="
echo "ModelGuard Lambda Deployment"
echo "=========================================="
echo "Bucket: $BUCKET_NAME"
echo "Table: $TABLE_NAME"
echo "Region: $REGION"
echo ""

# Step 1: Create S3 Bucket
echo "Step 1: Creating S3 bucket..."
aws s3 mb s3://$BUCKET_NAME --region $REGION || echo "Bucket may already exist"
echo "✓ S3 bucket created"

# Step 2: Create DynamoDB Table
echo ""
echo "Step 2: Creating DynamoDB table..."
aws dynamodb create-table \
  --table-name $TABLE_NAME \
  --attribute-definitions AttributeName=name,AttributeType=S \
  --key-schema AttributeName=name,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region $REGION \
  > /dev/null || echo "Table may already exist"
echo "✓ DynamoDB table created"

# Step 3: Create IAM Role
echo ""
echo "Step 3: Creating IAM role..."
# Create trust policy
cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
ROLE_ARN=$(aws iam create-role \
  --role-name ModelGuard-LambdaRole \
  --assume-role-policy-document file:///tmp/trust-policy.json \
  --query 'Role.Arn' --output text 2>/dev/null) || \
ROLE_ARN=$(aws iam get-role --role-name ModelGuard-LambdaRole --query 'Role.Arn' --output text)

echo "Role ARN: $ROLE_ARN"

# Create and attach policy
cat > /tmp/lambda-policy.json <<EOF
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
      "Resource": "arn:aws:s3:::${BUCKET_NAME}/*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem"],
      "Resource": "arn:aws:dynamodb:*:*:table/${TABLE_NAME}"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name ModelGuard-LambdaRole \
  --policy-name ModelGuard-LambdaPolicy \
  --policy-document file:///tmp/lambda-policy.json
echo "✓ IAM role created and configured"

# Wait for role to be ready
echo "Waiting for IAM role to propagate..."
sleep 10

# Step 4: Package Lambda
echo ""
echo "Step 4: Packaging Lambda function..."
rm -rf lambda-package lambda-deployment.zip
mkdir -p lambda-package
cp -r src lambda-package/
pip install -r requirements.txt -t lambda-package/ --quiet
cd lambda-package
zip -r ../lambda-deployment.zip . > /dev/null
cd ..
echo "✓ Lambda package created"

# Step 5: Create/Update Lambda Function
echo ""
echo "Step 5: Deploying Lambda function..."
LAMBDA_ARN=$(aws lambda create-function \
  --function-name $FUNCTION_NAME \
  --runtime python3.11 \
  --role $ROLE_ARN \
  --handler src.lambda_handlers.lambda_handler \
  --zip-file fileb://lambda-deployment.zip \
  --timeout 30 \
  --memory-size 256 \
  --environment Variables="{S3_BUCKET=${BUCKET_NAME},DYNAMODB_TABLE=${TABLE_NAME},AWS_REGION=${REGION}}" \
  --query 'FunctionArn' --output text 2>/dev/null) || \
LAMBDA_ARN=$(aws lambda update-function-code \
  --function-name $FUNCTION_NAME \
  --zip-file fileb://lambda-deployment.zip \
  --query 'FunctionArn' --output text)

echo "✓ Lambda function deployed: $LAMBDA_ARN"

# Step 6: Create API Gateway
echo ""
echo "Step 6: Creating API Gateway..."
API_ID=$(aws apigateway create-rest-api \
  --name $API_NAME \
  --query 'id' --output text 2>/dev/null) || \
API_ID=$(aws apigateway get-rest-apis --query "items[?name=='${API_NAME}'].id" --output text)

ROOT_ID=$(aws apigateway get-resources --rest-api-id $API_ID --query 'items[?path==`/`].id' --output text)

echo "✓ API Gateway created: $API_ID"

# Step 7: Create Resources and Methods (simplified)
echo ""
echo "Step 7: Configuring API Gateway resources..."
echo "Note: Full resource setup requires additional commands"
echo "See AWS_DEPLOYMENT_GUIDE.md for complete setup"

# Grant API Gateway permission
aws lambda add-permission \
  --function-name $FUNCTION_NAME \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:${REGION}:*:${API_ID}/*/*" \
  2>/dev/null || echo "Permission may already exist"

echo ""
echo "=========================================="
echo "Deployment Summary"
echo "=========================================="
echo "S3 Bucket: $BUCKET_NAME"
echo "DynamoDB Table: $TABLE_NAME"
echo "Lambda Function: $FUNCTION_NAME"
echo "Lambda ARN: $LAMBDA_ARN"
echo "API Gateway ID: $API_ID"
echo ""
echo "Next steps:"
echo "1. Complete API Gateway resource setup (see AWS_DEPLOYMENT_GUIDE.md)"
echo "2. Deploy API: aws apigateway create-deployment --rest-api-id $API_ID --stage-name prod"
echo "3. Test endpoints with curl commands"
echo ""
echo "To view logs:"
echo "aws logs tail /aws/lambda/$FUNCTION_NAME --follow"

