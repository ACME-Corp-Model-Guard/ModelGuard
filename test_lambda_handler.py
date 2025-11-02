#!/usr/bin/env python3
"""
Test script for Lambda handlers.
Tests both upload and download endpoints locally.
"""

import base64
import json
import os
from unittest.mock import MagicMock, patch

# Import the handler
from src.lambda_handlers import lambda_handler


def create_mock_event(method: str, path: str, path_params: dict = None, body: str = None, 
                     is_base64: bool = False, headers: dict = None, query_params: dict = None):
    """Create a mock API Gateway event."""
    event = {
        "httpMethod": method,
        "path": path,
        "pathParameters": path_params or {},
        "headers": headers or {},
        "queryStringParameters": query_params,
        "requestContext": {
            "http": {
                "method": method,
                "path": path
            }
        }
    }
    
    if body:
        event["body"] = body
        event["isBase64Encoded"] = is_base64
    
    return event


def test_upload_endpoint():
    """Test the POST /artifact/{artifact_type} endpoint."""
    print("\n" + "="*60)
    print("Testing POST /artifact/model - Upload Endpoint")
    print("="*60)
    
    # Create test file content
    test_file_content = b"This is a test model file content"
    test_model_name = "test-model-123"
    
    # Create multipart form data manually (simplified for testing)
    # In real usage, you'd use multipart/form-data
    # For testing, we'll use binary with header
    body_b64 = base64.b64encode(test_file_content).decode()
    
    event = create_mock_event(
        method="POST",
        path="/artifact/model",
        path_params={"artifact_type": "model"},
        body=body_b64,
        is_base64=True,
        headers={
            "Content-Type": "application/octet-stream",
            "X-Model-Name": test_model_name
        }
    )
    
    # Mock AWS services
    mock_s3_client = MagicMock()
    mock_dynamodb_client = MagicMock()
    
    # Mock DynamoDB - no existing model
    mock_dynamodb_client.get_item.return_value = {"Item": {}}
    
    with patch("src.lambda_handlers._get_aws_clients", return_value=(mock_s3_client, mock_dynamodb_client)):
        try:
            response = lambda_handler(event, None)
            
            print(f"\n✓ Handler executed successfully")
            print(f"Status Code: {response['statusCode']}")
            print(f"Response Body:")
            body = json.loads(response["body"])
            print(json.dumps(body, indent=2))
            
            if response["statusCode"] == 200:
                print("\n✓ Upload endpoint working correctly!")
            else:
                print(f"\n✗ Unexpected status code: {response['statusCode']}")
                
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()


def test_download_endpoint():
    """Test the GET /artifacts/{artifact_type}/{id} endpoint."""
    print("\n" + "="*60)
    print("Testing GET /artifacts/model/{id} - Download Endpoint")
    print("="*60)
    
    test_model_name = "test-model-123"
    test_s3_key = "model/test-model-123/abc123.pkl"
    test_file_content = b"This is the downloaded model file"
    
    # Create event
    event = create_mock_event(
        method="GET",
        path=f"/artifacts/model/{test_model_name}",
        path_params={
            "artifact_type": "model",
            "id": test_model_name
        },
        query_params={"metadata_only": "false"}
    )
    
    # Mock AWS services
    mock_s3_client = MagicMock()
    mock_dynamodb_client = MagicMock()
    
    # Mock DynamoDB - model exists
    mock_dynamodb_client.get_item.return_value = {
        "Item": {
            "name": {"S": test_model_name},
            "size": {"N": str(len(test_file_content))},
            "license": {"S": "unknown"},
            "model_key": {"S": test_s3_key},
            "code_key": {"S": ""},
            "dataset_key": {"S": ""},
            "scores": {"S": "{}"},
            "scores_latency": {"S": "{}"}
        }
    }
    
    # Mock S3 - file exists
    mock_s3_response = MagicMock()
    mock_s3_response["Body"].read.return_value = test_file_content
    mock_s3_response.get.return_value = "application/octet-stream"
    mock_s3_client.get_object.return_value = mock_s3_response
    
    with patch("src.lambda_handlers._get_aws_clients", return_value=(mock_s3_client, mock_dynamodb_client)):
        try:
            response = lambda_handler(event, None)
            
            print(f"\n✓ Handler executed successfully")
            print(f"Status Code: {response['statusCode']}")
            
            if response["statusCode"] == 200:
                print(f"Content-Type: {response['headers']['Content-Type']}")
                print(f"Is Base64 Encoded: {response.get('isBase64Encoded', False)}")
                
                # Decode the response
                if response.get("isBase64Encoded"):
                    decoded = base64.b64decode(response["body"])
                    print(f"Downloaded file size: {len(decoded)} bytes")
                    print(f"File content preview: {decoded[:50]}...")
                    print("\n✓ Download endpoint working correctly!")
                else:
                    body = json.loads(response["body"])
                    print(f"Response: {json.dumps(body, indent=2)}")
            else:
                print(f"\n✗ Unexpected status code: {response['statusCode']}")
                body = json.loads(response["body"])
                print(json.dumps(body, indent=2))
                
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()


def test_download_metadata_only():
    """Test the GET /artifacts/{artifact_type}/{id} endpoint with metadata_only=true."""
    print("\n" + "="*60)
    print("Testing GET /artifacts/model/{id}?metadata_only=true")
    print("="*60)
    
    test_model_name = "test-model-123"
    test_s3_key = "model/test-model-123/abc123.pkl"
    
    event = create_mock_event(
        method="GET",
        path=f"/artifacts/model/{test_model_name}",
        path_params={
            "artifact_type": "model",
            "id": test_model_name
        },
        query_params={"metadata_only": "true"}
    )
    
    # Mock AWS services
    mock_s3_client = MagicMock()
    mock_dynamodb_client = MagicMock()
    
    # Mock DynamoDB
    mock_dynamodb_client.get_item.return_value = {
        "Item": {
            "name": {"S": test_model_name},
            "size": {"N": "1000"},
            "license": {"S": "mit"},
            "model_key": {"S": test_s3_key},
            "code_key": {"S": "code/test-model-123/code.py"},
            "dataset_key": {"S": "dataset/test-model-123/data.csv"},
            "scores": {"S": '{"ramp_up_time": 0.8}'},
            "scores_latency": {"S": '{"ramp_up_time": 100}'}
        }
    }
    
    with patch("src.lambda_handlers._get_aws_clients", return_value=(mock_s3_client, mock_dynamodb_client)):
        try:
            response = lambda_handler(event, None)
            
            print(f"\n✓ Handler executed successfully")
            print(f"Status Code: {response['statusCode']}")
            
            if response["statusCode"] == 200:
                body = json.loads(response["body"])
                print("Response Body:")
                print(json.dumps(body, indent=2))
                print("\n✓ Metadata-only endpoint working correctly!")
            else:
                print(f"\n✗ Unexpected status code: {response['statusCode']}")
                body = json.loads(response["body"])
                print(json.dumps(body, indent=2))
                
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()


def test_error_handling():
    """Test error handling for invalid requests."""
    print("\n" + "="*60)
    print("Testing Error Handling")
    print("="*60)
    
    # Test invalid artifact type
    print("\n1. Testing invalid artifact_type...")
    event = create_mock_event(
        method="POST",
        path="/artifact/invalid",
        path_params={"artifact_type": "invalid"},
        body=base64.b64encode(b"test").decode(),
        is_base64=True
    )
    
    try:
        response = lambda_handler(event, None)
        body = json.loads(response["body"])
        print(f"   Status: {response['statusCode']}")
        print(f"   Error: {body.get('error')}")
        if response["statusCode"] == 400:
            print("   ✓ Invalid artifact type correctly rejected")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test missing model (404)
    print("\n2. Testing model not found...")
    event = create_mock_event(
        method="GET",
        path="/artifacts/model/non-existent",
        path_params={"artifact_type": "model", "id": "non-existent"}
    )
    
    mock_s3_client = MagicMock()
    mock_dynamodb_client = MagicMock()
    mock_dynamodb_client.get_item.return_value = {"Item": {}}
    
    with patch("src.lambda_handlers._get_aws_clients", return_value=(mock_s3_client, mock_dynamodb_client)):
        try:
            response = lambda_handler(event, None)
            body = json.loads(response["body"])
            print(f"   Status: {response['statusCode']}")
            print(f"   Error: {body.get('error')}")
            if response["statusCode"] == 404:
                print("   ✓ Missing model correctly handled")
        except Exception as e:
            print(f"   ✗ Error: {e}")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Lambda Handler Test Suite")
    print("="*60)
    print("\nNote: These tests use mocked AWS services.")
    print("For real AWS testing, set AWS credentials and remove mocks.")
    
    # Set environment variables for testing
    os.environ.setdefault("S3_BUCKET", "test-bucket")
    os.environ.setdefault("DYNAMODB_TABLE", "test-table")
    os.environ.setdefault("AWS_REGION", "us-east-1")
    
    try:
        test_upload_endpoint()
        test_download_endpoint()
        test_download_metadata_only()
        test_error_handling()
        
        print("\n" + "="*60)
        print("All tests completed!")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ Test suite error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

