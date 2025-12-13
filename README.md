# ModelGuard: A Trustworthy Model Registry

[![CI](https://github.com/ACME-Corp-Model-Guard/ModelGuard/actions/workflows/ci.yml/badge.svg)](https://github.com/ACME-Corp-Model-Guard/ModelGuard/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-LGPL%20v2.1-blue)](LICENSE)

ModelGuard is a secure, cloud-first ML model registry built on AWS serverless architecture. It provides trusted model storage, automated quality scoring, lineage tracking, and role-based access control for ML artifacts (models, datasets, code).

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [CI/CD](#cicd)
- [Frontend](#frontend)
- [License](#license)

---

## Overview

ModelGuard provides a centralized, trustworthy platform for managing machine learning artifacts. It allows users to:

- **Upload and download** models, datasets, and code from HuggingFace and GitHub
- **Rate models** using automated quality metrics (availability, bus factor, license, performance claims, etc.)
- **Search and enumerate** artifacts by name, regex, or ID
- **Track lineage** and dependencies between artifacts
- **Manage access** with role-based permissions (Admin/User groups)
- **Detect package confusion** for potentially malicious uploads

---

## Features

### Baseline Features

- **Artifact Management**: CRUD operations for models, datasets, and code
- **Quality Scoring**: Net scores computed from multiple metrics:
  - Availability, Bus Factor, Ramp Up Time
  - License compatibility, Performance Claims
  - Dataset Quality, Code Quality
  - Treescore (supply chain health)
  - Size scores (Raspberry Pi, Jetson Nano, Desktop PC, AWS Server)
- **Artifact Ingestion**: Import from HuggingFace (models/datasets) and GitHub (code)
- **Search**: Enumerate artifacts, search by name, regex queries
- **Lineage Tracking**: Graph of artifact dependencies and relationships
- **License Checks**: Compatibility verification between artifacts
- **Cost Estimation**: Size-based deployment cost metrics

### Security Track (Extended Features)

- **Role-Based Access Control**: Cognito-backed Admin and User groups
- **JWT Authentication**: Token-based API access with TTL and call limits
- **Sensitive Model Handling**: Download logging and monitoring
- **Package Confusion Detection**: Identifies potentially malicious packages
- **Replay Prevention**: Request fingerprinting to prevent duplicate operations

---

## Architecture

### Tech Stack

- **Backend**: Python 3.12, AWS Lambda, SAM
- **Frontend**: React 19, TypeScript, Vite, TanStack Router, Tailwind CSS
- **Database**: DynamoDB (metadata), S3 (artifact files)
- **Auth**: AWS Cognito with JWT tokens
- **AI/ML**: AWS Bedrock (Amazon Titan) for content analysis

### Project Structure

```
ModelGuard/
├── lambdas/              # Lambda handlers (one per API endpoint)
├── src/
│   ├── artifacts/        # Artifact classes (model, dataset, code)
│   │   └── artifactory/  # Factory, persistence, discovery
│   ├── metrics/          # Quality metrics (net_score, availability, etc.)
│   ├── storage/          # S3/DynamoDB utils, downloaders
│   ├── auth.py           # JWT validation, token management
│   └── logutil/          # Structured logging with Loguru
├── frontend/             # React/TypeScript frontend
├── tests/                # Pytest test suite
├── scripts/              # Utility scripts
└── template.yaml         # SAM/CloudFormation template
```

### AWS Services

| Service | Purpose |
|---------|---------|
| Lambda | Serverless API handlers |
| API Gateway | REST API routing |
| DynamoDB | Artifact metadata, tokens, fingerprints |
| S3 | Artifact file storage |
| Cognito | User authentication and groups |
| Bedrock | LLM-powered content analysis |
| CloudFront | Frontend CDN |
| CloudWatch | Logging and monitoring |

---

## Installation

### Prerequisites

- Python 3.12+
- AWS CLI configured with appropriate credentials
- AWS SAM CLI
- Node.js 18+ (for frontend)

### Backend Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or use the run script
./run install
```

### Deployment

```bash
# Build SAM application
sam build --cached --parallel

# Deploy to AWS
sam deploy --no-confirm-changeset --parameter-overrides DeploymentRegion=us-east-2
```

---

## Usage

### Authentication

All API endpoints (except `/health`, `/tracks`, `/authenticate`) require the `X-Authorization` header:

```bash
# Get authentication token
curl -X PUT https://your-api.amazonaws.com/dev/authenticate \
  -H "Content-Type: application/json" \
  -d '{"User": {"name": "username", "isAdmin": false}, "Secret": {"password": "password"}}'

# Use token in subsequent requests
curl https://your-api.amazonaws.com/dev/artifacts/model/123 \
  -H "X-Authorization: bearer <token>"
```

### Upload an Artifact

```bash
# Upload a model from HuggingFace
curl -X POST https://your-api.amazonaws.com/dev/artifact/model \
  -H "X-Authorization: bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"URL": "https://huggingface.co/microsoft/resnet-50"}'

# Upload code from GitHub
curl -X POST https://your-api.amazonaws.com/dev/artifact/code \
  -H "X-Authorization: bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"URL": "https://github.com/owner/repo"}'
```

### Rate a Model

```bash
curl https://your-api.amazonaws.com/dev/artifact/model/<id>/rate \
  -H "X-Authorization: bearer <token>"
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/tracks` | List implemented tracks |
| PUT | `/authenticate` | Get auth token |
| POST | `/artifacts` | Enumerate/query artifacts |
| POST | `/artifact/{type}` | Upload new artifact |
| GET | `/artifacts/{type}/{id}` | Download artifact |
| PUT | `/artifacts/{type}/{id}` | Update artifact |
| GET | `/artifact/{type}/{id}/cost` | Get size cost |
| GET | `/artifact/model/{id}/rate` | Get model ratings |
| GET | `/artifact/model/{id}/lineage` | Get lineage graph |
| POST | `/artifact/model/{id}/license-check` | License compatibility |
| GET | `/artifact/byName/{name}` | Search by name |
| POST | `/artifact/byRegEx` | Regex search |
| DELETE | `/reset` | Reset system |

Full API specification: [`ece461_fall_2025_openapi_spec.yaml`](ece461_fall_2025_openapi_spec.yaml)

---

## Testing

```bash
# Run tests with summary
./run test

# Run tests with coverage report
./run testall

# Or manually
python -m pytest tests/ -v
python -m coverage run -m pytest tests/
python -m coverage report

# Run specific test file
pytest tests/test_auth.py -v

# Run specific test function
pytest tests/test_auth.py::test_authenticate_user -v
```

### Code Quality

```bash
# Formatting
black .
black --check .

# Linting
flake8 .

# Type checking
mypy .
```

---

## CI/CD

### CI Pipeline (Pull Requests)

1. Black formatting check
2. Flake8 linting
3. Mypy type checking
4. Pytest test suite

### Deployment Pipeline (Push to main)

1. SAM build and deploy backend
2. Generate frontend Cognito config
3. Build frontend with Vite
4. Sync to S3 and invalidate CloudFront

Pull requests require at least one independent code review.

---

## Frontend

> **Note**: Frontend is currently under development by a team member.

The current frontend is a React 19 + TypeScript application using:
- TanStack Router (file-based routing)
- Radix UI + Tailwind CSS + shadcn/ui
- react-oidc-context for Cognito authentication

```bash
cd frontend
npm ci
npm run dev    # Development server on port 3000
npm run build  # Production build
```

---

## License

This project is licensed under the LGPL v2.1. See [LICENSE](LICENSE) for details.
