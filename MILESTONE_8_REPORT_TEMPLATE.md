# Milestone 8 Delivery MVP Report

**Team Members:**
- Ryan Austin
- Cody Hatfield
- Kyle Horn
- Austin Schultz

**Date:** November 2nd, 2025

---

## 1. CI/CD Demo

### Continuous Integration (CI)

Our system uses GitHub Actions to run automated tests on every pull request.

**Location:** `.github/workflows/ci.yml`

**What Runs:**
1. **Code Formatting Check (Black)**
   - Ensures consistent code formatting across the codebase
   - Fails PR if code doesn't meet formatting standards

2. **Linting (flake8)**
   - Syntax error detection (E9, F63, F7, F82)
   - Code complexity checks (max complexity: 10)
   - Line length validation (max 127 characters)

3. **Type Checking (mypy)**
   - Static type analysis for Python code
   - Validates type annotations across all modules

4. **Automated Testing (pytest)**
   - Runs all unit tests in `tests/` directory
   - Generates coverage reports
   - Uploads coverage XML as artifact

**Screenshot Required:**
- Screenshot of GitHub Actions workflow running on a PR
- Show the check marks for all 4 steps above

### Continuous Deployment (CD)

**Status:** [ ] Implemented / [ ] Partial / [ ] Not Yet Implemented

**If Implemented:**
- How: [Describe deployment method]
  - Example: "Uses AWS SAM CLI to deploy Lambda functions automatically after merge to main"
  - Example: "Builds Docker container, pushes to ECR, updates Lambda functions"

**Screenshot Required:**
- Screenshot of GitHub Actions workflow deploying to AWS after merge
- Show deployment steps completing successfully

**If Not Yet Implemented:**
- Current Status: [Describe manual deployment process]
- Plan: [How you plan to automate deployment]

---

## 2. MVP Delivery

### 2.1 Upload Endpoint (`POST /artifact/{artifact_type}`)

**Status:** ✅ Implemented

**File:** `lambdas/post_artifact_upload.py`

**What It Does:**
- Accepts artifact uploads (model, code, or dataset)
- Uploads file to S3 bucket
- Creates/updates model metadata in DynamoDB
- Computes scores for new models using metrics system
- Returns artifact metadata including S3 key

**What Works:**
- ✅ Accepts multipart/form-data or binary uploads
- ✅ Handles model, code, and dataset types
- ✅ Stores files in S3 with structured paths: `{artifact_type}/{model_name}/{uuid}.ext`
- ✅ Creates new models in DynamoDB or updates existing ones
- ✅ Computes initial scores for new models
- ✅ Returns success response with metadata

**What Doesn't Work / Missing:**
- ⚠️ [List any known issues]
  - Example: "Unique ID generation - currently uses model name as artifact_id"
  - Example: "HuggingFace integration - placeholder for now"
  - Example: "File size validation - no limits enforced"

**Screenshot/Evidence:**
```
Screenshot of terminal showing:
1. curl POST request to upload endpoint
2. Response showing success with metadata
3. Or Postman/API testing tool showing request/response
```

**Example Request:**
```bash
curl -X POST "https://YOUR-API.execute-api.us-east-1.amazonaws.com/dev/artifact/model" \
  -H "Content-Type: application/octet-stream" \
  -H "X-Model-Name: bert-base-uncased" \
  --data-binary "@model.pkl"
```

**Example Response:**
```json
{
  "message": "Artifact uploaded successfully",
  "artifact_type": "model",
  "model_name": "bert-base-uncased",
  "s3_key": "model/bert-base-uncased/uuid-here.pkl",
  "model": {
    "name": "bert-base-uncased",
    "size": 420000000,
    "license": "unknown",
    "model_key": "model/bert-base-uncased/uuid-here.pkl",
    "scores": {...},
    "scores_latency": {...}
  }
}
```

---

### 2.2 Search/Get Artifact Endpoint

**Status:** ✅ Implemented

**File:** `lambdas/get_artifact_download.py`

**Endpoint:** `GET /artifacts/{artifact_type}/{id}`

**What It Does:**
- Retrieves artifact by type and ID (model name)
- Downloads file from S3 or returns metadata only
- Supports query parameter `metadata_only=true` for metadata-only responses

**Why This Endpoint:**
- Demonstrates core artifact retrieval functionality
- Shows integration between API Gateway → Lambda → DynamoDB → S3
- Supports both binary file downloads and metadata queries
- Essential for MVP as it complements the upload endpoint

**What Works:**
- ✅ Loads model from DynamoDB by artifact_id (model name)
- ✅ Downloads artifact file from S3
- ✅ Returns binary file (base64-encoded for API Gateway)
- ✅ Returns JSON metadata when `metadata_only=true`
- ✅ Proper error handling (404 for missing models/artifacts)

**What Doesn't Work / Missing:**
- ⚠️ [List any known issues]
  - Example: "Search by regex not fully implemented"
  - Example: "No pagination for large result sets"
  - Example: "Authentication not enforced (stub implementation)"

**Alternative Endpoints:**
- `GET /artifact/byName/{name}` - `lambdas/get_search_by_name.py`
- `POST /artifact/byRegEx` - `lambdas/post_search_by_regex.py`
- `POST /artifacts` - `lambdas/post_artifacts.py` (enumerate)

**Screenshot/Evidence:**
```
Screenshot showing:
1. GET request to download endpoint
2. Response with file download or metadata
3. Show both metadata_only=true and full download examples
```

**Example Request:**
```bash
# Get metadata only
curl "https://YOUR-API.execute-api.us-east-1.amazonaws.com/dev/artifacts/model/bert-base-uncased?metadata_only=true"

# Download file
curl "https://YOUR-API.execute-api.us-east-1.amazonaws.com/dev/artifacts/model/bert-base-uncased" \
  -o downloaded_model.pkl
```

---

### 2.3 AWS Deployment

**Status:** ✅ Deployed

**Backend URL:** 
```
https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/dev/
```

**Frontend URL:**
```
https://YOUR-AMPLIFY-APP.amplifyapp.com
```
(Set up by Ryan via AWS Amplify)

**How to Get API URL:**
1. After `sam deploy`, check output for `ModelGuardApi` URL
2. Or check AWS Console → API Gateway → APIs → ModelGuardApi → Stages → dev

**Infrastructure (SAM Template):**
- DynamoDB Table: `ModelGuard-Artifacts-Metadata`
- S3 Bucket: `modelguard-artifacts-files`
- API Gateway: REST API with multiple endpoints
- Lambda Functions: Individual functions per endpoint

---

### 2.4 Autograder Integration

**Status:** ✅ Registered

**Screenshot Required:**
1. Autograder dashboard showing:
   - Backend URL registered
   - Frontend URL registered
   - Last run timestamp and status

**Screenshot of Last Run:**
- Show autograder test results
- Even if score is low, showing you scheduled a run is sufficient
- Note any specific failures or successes

**Optional: Log Screenshot:**
- CloudWatch logs showing autograder requests hitting your system
- Shows actual traffic/requests being processed

---

## 3. Additional Functionality Status

### Implemented
- ✅ Core upload/download endpoints
- ✅ S3 integration for artifact storage
- ✅ DynamoDB integration for metadata
- ✅ Model scoring system (11 metrics + NetScore)
- ✅ Modular Lambda function structure
- ✅ SAM template for infrastructure as code
- ✅ React frontend (migrated by Ryan)

### In Progress
- ⏳ Authentication (Cognito integration - Ryan working on)
- ⏳ Search by regex (endpoint exists, may need refinement)
- ⏳ HuggingFace integration (design in progress - Cody)

### Planned/Not Started
- 📋 Full authentication enforcement
- 📋 Package confusion detection
- 📋 Download monitoring/JavaScript execution
- 📋 Lineage tracking

---

## 4. Are You On Track?

### Progress Assessment

**Target:** Deliver MVP with upload and search endpoints

**Current Status:** ✅ **ON TRACK**

**Evidence:**
- Core endpoints implemented and tested
- Infrastructure deployed to AWS
- CI pipeline operational
- Frontend integrated with backend

**Timeline:**

| Task | Target | Status | Notes |
|------|--------|--------|-------|
| Upload Endpoint | ✅ | Complete | POST /artifact/{artifact_type} working |
| Download/Search Endpoint | ✅ | Complete | GET /artifacts/{artifact_type}/{id} working |
| AWS Deployment | ✅ | Complete | SAM template deployed |
| Autograder Registration | ✅ | Complete | URLs registered, runs scheduled |
| CI/CD Pipeline | ✅ | Complete | CI working, CD in progress |
| Frontend | ✅ | Complete | React app deployed via Amplify |

### If Behind Schedule

**Remediation Plan:**
- [Describe plan if behind]
- Example: "Focus on MVP endpoints first, defer extended features"
- Example: "Pair programming sessions to accelerate development"

---

## 5. Design Changes

### Substantial Changes?

**Status:** Minor adjustments, core design intact

**Changes Made:**
1. **Lambda Structure:**
   - Changed from unified handler to modular per-endpoint structure
   - Better matches AWS SAM best practices
   - Easier to maintain and deploy individually

2. **Environment Variables:**
   - Standardized on `ARTIFACTS_BUCKET` and `ARTIFACTS_TABLE`
   - Set via SAM template automatically

3. **DynamoDB Schema:**
   - Using `artifact_id` as primary key (maps to model name)
   - Storing scores as JSON strings (DynamoDB limitation)

**What Stayed the Same:**
- Core Model class structure
- Metrics system design
- S3 storage patterns
- API Gateway routing

**Rationale:**
- Changes improve maintainability and AWS best practices
- Don't affect core functionality or user experience
- Align with team's modular architecture goals

---

## 6. Non-Technical Issues

**Status:** No major issues reported

**Team Communication:**
- ✅ Regular updates in Discord
- ✅ Code reviews via PRs
- ✅ Clear task assignments

**Challenges:**
- [Document any challenges if applicable]
- Example: "Initial Docker setup took longer than expected"
- Example: "Coordinating deployment timing across team members"

**Resolutions:**
- [How challenges were resolved]
- Example: "Ryan documented local testing setup in Loop"
- Example: "Pair programming session helped resolve integration issues"

---

## 7. Evidence Checklist

Before submitting, ensure you have:

- [ ] Screenshot of CI pipeline running tests (GitHub Actions)
- [ ] Screenshot of CD pipeline deploying (if implemented)
- [ ] Screenshot of POST upload request/response
- [ ] Screenshot of GET download/search request/response
- [ ] Screenshot of Autograder dashboard with registered URLs
- [ ] Screenshot of Autograder last run results
- [ ] Backend API Gateway URL
- [ ] Frontend Amplify URL
- [ ] Notes on what works/what doesn't for each endpoint

---

## Appendix: Quick Reference

### Endpoints Implemented

| Endpoint | Method | Handler | Status |
|----------|--------|---------|--------|
| `/artifact/{artifact_type}` | POST | `post_artifact_upload.py` | ✅ |
| `/artifacts/{artifact_type}/{id}` | GET | `get_artifact_download.py` | ✅ |
| `/artifact/byName/{name}` | GET | `get_search_by_name.py` | ✅ |
| `/artifact/byRegEx` | POST | `post_search_by_regex.py` | 🔄 |
| `/artifacts` | POST | `post_artifacts.py` | 🔄 |
| `/artifacts/{artifact_type}/{id}` | PUT | `put_artifact_update.py` | 🔄 |
| `/model/{id}/rate` | GET | `get_model_rate.py` | 🔄 |

### Local Testing Commands

```bash
# Build and run locally
sam build
sam local start-api

# Test endpoints
curl http://127.0.0.1:3000/artifact/model -X POST -H "X-Model-Name: test" --data-binary "@file.txt"
curl http://127.0.0.1:3000/artifacts/model/test?metadata_only=true
```

### Deployment Commands

```bash
# Deploy to AWS
sam build
sam deploy --guided  # First time
sam deploy           # Subsequent
```

