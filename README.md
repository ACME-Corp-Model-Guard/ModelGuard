# ModelGuard: A Trustworthy Model Registry

[![License](https://img.shields.io/badge/license-LGPL%20v2.1-blue)](LICENSE)

ModelGuard is a secure, cloud-first registry for storing, rating, and distributing machine learning models. It is designed to address shortcomings in third-party model repositories by supporting private trusted models, automated scoring, lineage tracking, and secure access control.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
  - [Baseline Features](#baseline-features)
  - [Extended Features](#extended-features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
  - [Web Interface](#web-interface)
  - [REST API](#rest-api)
- [Testing](#testing)
- [CI/CD](#cicd)
- [Security Considerations](#security-considerations)
- [License](#license)
- [Contributing](#contributing)

---

## Overview

ModelGuard provides a centralized, trustworthy platform for managing machine learning models. It allows users to:

- Upload and download models (full or partial packages)
- Rate models using a variety of quality metrics
- Search and enumerate models
- Track lineage and dependencies
- Manage access for sensitive models
- Detect potential malicious package uploads

This system integrates AWS services, including Lambda, S3, API Gateway, SageMaker, and CloudWatch for deployment, observability, and model evaluation.

---

## Features

### Baseline Features

- **CRUD operations** for model zip packages
- **Rating**: Computes net scores and sub-scores including:
  - Reproducibility
  - Reviewedness
  - Treescore
- **Model ingestion** from HuggingFace with score validation
- **Model enumeration** with regex and version queries
- **Lineage graph** tracking
- **Size and license checks**
- **Reset**: Restore system to default state
- **Interfaces**:
  - RESTful API compliant with OpenAPI
  - Web browser interface

### Extended Features

ModelGuard focuses on the **Security Track**:

- **User-Based Access Control (RBAC)**: Fine-grained permissions for uploads, downloads, and administrative actions
- **Sensitive Models**: Support for executing monitoring JavaScript prior to downloads and logging download history
- **Package Confusion Detection**: Identifies potentially malicious packages based on metadata, usage, and anomalous download patterns

---

## Architecture

ModelGuard is implemented as a modular system using Python 3.12 with the following components:

- **`src/model.py`**: Core `Model` class handling model metadata and scoring
- **`src/metrics/`**: Implements baseline and extended model metrics
- **`lambdas/`**: AWS Lambda functions serving API endpoints
- **`web/`**: Undecided framework!!!
- **AWS Components**:
  - **Lambda**: Serverless compute for API requests
  - **S3**: Versioned object storage for models
  - **API Gateway**: Front door for REST API
  - **CloudWatch & X-Ray**: Observability and logging
  - **SageMaker / Bedrock**: Model evaluation and LLM integration
  - **Cognito**: User accounts and authentication
  - **Parameter Store**: Secure storage of secrets and credentials

---

## CI/CD

GitHub Actions are used for:
- automated unit and integration tests
- deployment to AWS Lambda and associated services
- health checks post-deployment

Pull requests require at least one independent code review.

---

## License

This project is licensed under the LGPL v2.1. See LICENSE for details.