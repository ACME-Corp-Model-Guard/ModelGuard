# How the Lambda Handler Works

## Overview

The Lambda handler (`src/lambda_handlers.py`) provides two main endpoints for artifact management:

1. **POST /artifact/{artifact_type}** - Upload artifacts to S3
2. **GET /artifacts/{artifact_type}/{id}** - Retrieve artifacts from S3

## Request Flow

### Entry Point: `lambda_handler()`

```python
# Main router that handles all incoming API Gateway requests
def lambda_handler(event, context):
    http_method = event.get("httpMethod")
    path = event.get("path")
    
    # Route to appropriate handler
    if http_method == "GET" and "/artifacts/" in path:
        return get_artifact_handler(event, context)
    elif http_method == "POST" and "/artifact/" in path:
        return upload_artifact_handler(event, context)
    else:
        return _error_response(404, "Not found")
```

---

## 1. Upload Flow (POST /artifact/{artifact_type})

### Step-by-Step Flow:

```
┌─────────────────┐
│  API Gateway    │
│  POST Request   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  lambda_handler()      │
│  Routes to:             │
│  upload_artifact_handler│
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 1. Extract path params  │
│    artifact_type: model │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 2. Parse request body   │
│    - multipart/form-data │
│    - or binary           │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 3. Extract model name   │
│    - from form field     │
│    - from header         │
│    - or generate UUID    │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 4. Upload to S3         │
│    _upload_to_s3()       │
│    Key: model/name/uuid │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 5. Load/Create Model    │
│    from DynamoDB         │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 6. Update Model keys    │
│    - model.model_key     │
│    - model.code_key      │
│    - model.dataset_key   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 7. Save to DynamoDB    │
│    _save_model_to_dynamodb│
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 8. Return success       │
│    JSON with metadata    │
└─────────────────────────┘
```

### Example Request:

```bash
POST /artifact/model
Content-Type: multipart/form-data

Form Data:
- file: model.pkl (binary)
- model_name: "bert-base"
```

### Example Response:

```json
{
  "statusCode": 200,
  "headers": {...},
  "body": {
    "message": "Artifact uploaded successfully",
    "artifact_type": "model",
    "model_name": "bert-base",
    "s3_key": "model/bert-base/a1b2c3d4.pkl",
    "model": {
      "name": "bert-base",
      "size": 420000000,
      "license": "unknown",
      "model_key": "model/bert-base/a1b2c3d4.pkl",
      "code_key": "",
      "dataset_key": "",
      "scores": {},
      "scores_latency": {}
    }
  }
}
```

---

## 2. Download Flow (GET /artifacts/{artifact_type}/{id})

### Step-by-Step Flow:

```
┌─────────────────┐
│  API Gateway    │
│  GET Request    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  lambda_handler()      │
│  Routes to:             │
│  get_artifact_handler   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 1. Extract path params  │
│    artifact_type: model │
│    id: "bert-base"      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 2. Check query params   │
│    metadata_only: true?  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 3. Load Model from      │
│    DynamoDB by ID        │
│    _load_model_from_     │
│    dynamodb()            │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 4. Get S3 key from Model│
│    model.model_key      │
│    model.code_key       │
│    model.dataset_key    │
└────────┬────────────────┘
         │
         ▼
         ├─────────────────────────────┐
         │                             │
         ▼                             ▼
┌────────────────────┐    ┌────────────────────┐
│ metadata_only=true?│    │ metadata_only=false │
│ Return JSON only   │    │ Download file      │
└────────────────────┘    └────────┬───────────┘
                                    │
                                    ▼
                          ┌────────────────────┐
                          │ _download_from_s3()│
                          └────────┬───────────┘
                                    │
                                    ▼
                          ┌────────────────────┐
                          │ Return binary file  │
                          │ (base64-encoded)   │
                          └────────────────────┘
```

### Example Requests:

#### Get File:
```bash
GET /artifacts/model/bert-base
```

**Response:**
- Binary file (base64-encoded)
- Content-Type: application/octet-stream
- Body: base64-encoded file content

#### Get Metadata Only:
```bash
GET /artifacts/model/bert-base?metadata_only=true
```

**Response:**
```json
{
  "statusCode": 200,
  "headers": {...},
  "body": {
    "artifact_type": "model",
    "model_name": "bert-base",
    "s3_key": "model/bert-base/a1b2c3d4.pkl",
    "model": {
      "name": "bert-base",
      "size": 420000000,
      "license": "unknown",
      "model_key": "model/bert-base/a1b2c3d4.pkl",
      "scores": {...},
      "scores_latency": {...}
    }
  }
}
```

---

## Key Helper Functions

### AWS Integration

```python
# Initialize AWS clients (lazy loading)
def _get_aws_clients():
    global s3_client, dynamodb_client
    if s3_client is None:
        s3_client = boto3.client("s3")
    if dynamodb_client is None:
        dynamodb_client = boto3.client("dynamodb")
    return s3_client, dynamodb_client
```

### S3 Operations

```python
# Upload file to S3
def _upload_to_s3(artifact_type, model_name, file_content, filename):
    s3_key = f"{artifact_type}/{model_name}/{uuid.uuid4()}{ext}"
    s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=file_content)
    return s3_key

# Download file from S3
def _download_from_s3(s3_key):
    response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
    return response["Body"].read(), response.get("ContentType")
```

### DynamoDB Operations

```python
# Save Model to DynamoDB
def _save_model_to_dynamodb(model):
    model_dict = model.to_dict()
    # Convert to DynamoDB format (String, Number types)
    dynamodb.put_item(TableName=DYNAMODB_TABLE, Item=dynamodb_item)

# Load Model from DynamoDB
def _load_model_from_dynamodb(model_name):
    response = dynamodb.get_item(TableName=DYNAMODB_TABLE, Key={"name": model_name})
    # Convert from DynamoDB format back to Model
    return Model.from_dict(model_dict)
```

---

## Error Handling

The handler returns consistent error responses:

```python
def _error_response(status_code, message, error_code=None):
    return {
        "statusCode": status_code,
        "headers": {...},
        "body": {
            "error": message,
            "error_code": error_code
        }
    }
```

### Common Errors:

- **400 Bad Request**: Invalid artifact type, missing body, missing ID
- **404 Not Found**: Model not found, artifact not found
- **500 Internal Server Error**: S3 upload/download failure, DynamoDB save failure

---

## Response Formats

### JSON Response (for metadata):
```python
_create_response(200, {"message": "success", ...})
```

### Binary Response (for file downloads):
```python
_create_binary_response(200, file_bytes, "application/octet-stream")
# Returns base64-encoded body with isBase64Encoded=True
```

---

## Testing Locally

### Mock Event for Upload:

```python
event = {
    "httpMethod": "POST",
    "path": "/artifact/model",
    "pathParameters": {"artifact_type": "model"},
    "headers": {
        "content-type": "multipart/form-data",
        "X-Model-Name": "test-model"
    },
    "body": base64.b64encode(b"model content").decode(),
    "isBase64Encoded": True
}

response = lambda_handler(event, None)
```

### Mock Event for Download:

```python
event = {
    "httpMethod": "GET",
    "path": "/artifacts/model/test-model",
    "pathParameters": {
        "artifact_type": "model",
        "id": "test-model"
    },
    "queryStringParameters": {"metadata_only": "false"}
}

response = lambda_handler(event, None)
```

---

## Environment Variables

Required configuration (can be set in Lambda environment):

- `S3_BUCKET`: S3 bucket name (default: "modelguard-artifacts")
- `DYNAMODB_TABLE`: DynamoDB table name (default: "ModelGuard-Models")
- `AWS_REGION`: AWS region (default: "us-east-1")

---

## Integration with Existing Code

The handler uses your existing `Model` class:

```python
from src.model import Model

# Create model
model = Model(name="bert-base", model_key="...", code_key="...", dataset_key="...")

# Convert to dict for DynamoDB
model_dict = model.to_dict()

# Load from dict
model = Model.from_dict(model_dict)
```

This ensures consistency with the rest of your codebase!

