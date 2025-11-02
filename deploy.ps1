# PowerShell deployment script for ModelGuard Lambda handler
# Run with: .\deploy.ps1

param(
    [string]$BucketName = "modelguard-artifacts-$(Get-Random)",
    [string]$TableName = "ModelGuard-Models",
    [string]$Region = "us-east-1",
    [string]$FunctionName = "ModelGuard-ArtifactHandler"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "ModelGuard Lambda Deployment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Bucket: $BucketName"
Write-Host "Table: $TableName"
Write-Host "Region: $Region"
Write-Host ""

# Step 1: Create S3 Bucket
Write-Host "Step 1: Creating S3 bucket..." -ForegroundColor Yellow
try {
    aws s3 mb "s3://$BucketName" --region $Region 2>&1 | Out-Null
    Write-Host "✓ S3 bucket created" -ForegroundColor Green
} catch {
    Write-Host "! Bucket may already exist or error occurred" -ForegroundColor Yellow
}

# Step 2: Create DynamoDB Table
Write-Host ""
Write-Host "Step 2: Creating DynamoDB table..." -ForegroundColor Yellow
try {
    aws dynamodb create-table `
        --table-name $TableName `
        --attribute-definitions AttributeName=name,AttributeType=S `
        --key-schema AttributeName=name,KeyType=HASH `
        --billing-mode PAY_PER_REQUEST `
        --region $Region 2>&1 | Out-Null
    Write-Host "✓ DynamoDB table created" -ForegroundColor Green
    Write-Host "  Waiting for table to be active..." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
} catch {
    Write-Host "! Table may already exist" -ForegroundColor Yellow
}

# Step 3: Create IAM Role
Write-Host ""
Write-Host "Step 3: Creating IAM role..." -ForegroundColor Yellow

# Create trust policy
$trustPolicy = @{
    Version = "2012-10-17"
    Statement = @(
        @{
            Effect = "Allow"
            Principal = @{
                Service = "lambda.amazonaws.com"
            }
            Action = "sts:AssumeRole"
        }
    )
} | ConvertTo-Json -Depth 10

$trustPolicy | Out-File -FilePath "$env:TEMP\trust-policy.json" -Encoding utf8

try {
    $roleOutput = aws iam create-role `
        --role-name ModelGuard-LambdaRole `
        --assume-role-policy-document file://"$env:TEMP\trust-policy.json" `
        --query 'Role.Arn' --output text 2>&1
    $RoleARN = $roleOutput.Trim()
} catch {
    $RoleARN = (aws iam get-role --role-name ModelGuard-LambdaRole --query 'Role.Arn' --output text).Trim()
}

Write-Host "  Role ARN: $RoleARN" -ForegroundColor Gray

# Create policy
$policy = @{
    Version = "2012-10-17"
    Statement = @(
        @{
            Effect = "Allow"
            Action = @("logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents")
            Resource = "arn:aws:logs:*:*:*"
        },
        @{
            Effect = "Allow"
            Action = @("s3:PutObject", "s3:GetObject")
            Resource = "arn:aws:s3:::$BucketName/*"
        },
        @{
            Effect = "Allow"
            Action = @("dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:UpdateItem")
            Resource = "arn:aws:dynamodb:*:*:table/$TableName"
        }
    )
} | ConvertTo-Json -Depth 10

$policy | Out-File -FilePath "$env:TEMP\lambda-policy.json" -Encoding utf8

aws iam put-role-policy `
    --role-name ModelGuard-LambdaRole `
    --policy-name ModelGuard-LambdaPolicy `
    --policy-document file://"$env:TEMP\lambda-policy.json" | Out-Null

Write-Host "✓ IAM role created and configured" -ForegroundColor Green
Write-Host "  Waiting for IAM role to propagate..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Step 4: Package Lambda
Write-Host ""
Write-Host "Step 4: Packaging Lambda function..." -ForegroundColor Yellow

if (Test-Path "lambda-package") {
    Remove-Item -Recurse -Force "lambda-package"
}
if (Test-Path "lambda-deployment.zip") {
    Remove-Item -Force "lambda-deployment.zip"
}

New-Item -ItemType Directory -Path "lambda-package" | Out-Null
Copy-Item -Recurse -Path "src" -Destination "lambda-package\" | Out-Null

Write-Host "  Installing dependencies..." -ForegroundColor Gray
pip install -r requirements.txt -t lambda-package\ --quiet 2>&1 | Out-Null

Write-Host "  Creating deployment package..." -ForegroundColor Gray
Compress-Archive -Path "lambda-package\*" -DestinationPath "lambda-deployment.zip" -Force | Out-Null

$zipSize = (Get-Item "lambda-deployment.zip").Length / 1MB
Write-Host "✓ Lambda package created ($([math]::Round($zipSize, 2)) MB)" -ForegroundColor Green

# Step 5: Create/Update Lambda Function
Write-Host ""
Write-Host "Step 5: Deploying Lambda function..." -ForegroundColor Yellow

$envVars = "S3_BUCKET=$BucketName,DYNAMODB_TABLE=$TableName,AWS_REGION=$Region"

try {
    $lambdaArn = aws lambda create-function `
        --function-name $FunctionName `
        --runtime python3.11 `
        --role $RoleARN `
        --handler src.lambda_handlers.lambda_handler `
        --zip-file fileb://lambda-deployment.zip `
        --timeout 30 `
        --memory-size 256 `
        --environment Variables="{`"S3_BUCKET`":`"$BucketName`",`"DYNAMODB_TABLE`":`"$TableName`",`"AWS_REGION`":`"$Region`"}" `
        --query 'FunctionArn' --output text 2>&1
    $LambdaARN = $lambdaArn.Trim()
} catch {
    Write-Host "  Function exists, updating code..." -ForegroundColor Yellow
    aws lambda update-function-code `
        --function-name $FunctionName `
        --zip-file fileb://lambda-deployment.zip | Out-Null
    
    aws lambda update-function-configuration `
        --function-name $FunctionName `
        --environment Variables="{`"S3_BUCKET`":`"$BucketName`",`"DYNAMODB_TABLE`":`"$TableName`",`"AWS_REGION`":`"$Region`"}" | Out-Null
    
    $LambdaARN = (aws lambda get-function --function-name $FunctionName --query 'Configuration.FunctionArn' --output text).Trim()
}

Write-Host "✓ Lambda function deployed: $LambdaARN" -ForegroundColor Green

# Step 6: Create API Gateway
Write-Host ""
Write-Host "Step 6: Creating API Gateway..." -ForegroundColor Yellow

try {
    $apiId = aws apigateway create-rest-api `
        --name "ModelGuard-API" `
        --query 'id' --output text 2>&1
    $APIID = $apiId.Trim()
} catch {
    $APIID = (aws apigateway get-rest-apis --query "items[?name=='ModelGuard-API'].id" --output text).Trim()
}

Write-Host "✓ API Gateway created: $APIID" -ForegroundColor Green
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deployment Summary" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "S3 Bucket: $BucketName" -ForegroundColor White
Write-Host "DynamoDB Table: $TableName" -ForegroundColor White
Write-Host "Lambda Function: $FunctionName" -ForegroundColor White
Write-Host "Lambda ARN: $LambdaARN" -ForegroundColor White
Write-Host "API Gateway ID: $APIID" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Complete API Gateway resource setup (see AWS_DEPLOYMENT_GUIDE.md)" -ForegroundColor Gray
Write-Host "2. Deploy API: aws apigateway create-deployment --rest-api-id $APIID --stage-name prod" -ForegroundColor Gray
Write-Host "3. Test endpoints with curl commands" -ForegroundColor Gray
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "aws logs tail /aws/lambda/$FunctionName --follow" -ForegroundColor Gray

