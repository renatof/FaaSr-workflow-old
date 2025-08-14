# FaaSr CLI - GitHub Actions Workflows Guide

This repository contains two powerful GitHub Actions workflows for deploying and triggering FaaSr (Function-as-a-Service for R) functions across multiple cloud platforms.

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Workflows](#workflows)
  - [Deploy Functions Workflow](#deploy-functions-workflow)
  - [Trigger Function Workflow](#trigger-function-workflow)
- [Configuration Files](#configuration-files)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)

## 🔍 Overview

The FaaSr CLI provides two main workflows:

1. **Deploy Functions** (`deploy-functions.yml`) - Deploys your FaaSr functions to supported cloud platforms
2. **Trigger Function** (`trigger-function.yml`) - Executes deployed functions with your workflow configuration

### Supported Platforms

- **AWS Lambda** - Serverless compute on Amazon Web Services
- **GitHub Actions** - Native GitHub workflow execution
- **OpenWhisk** - Open-source serverless platform

## 🛠 Prerequisites

Before using these workflows, ensure you have:

1. A GitHub repository with the FaaSr CLI code
2. Appropriate cloud platform accounts and credentials
3. Workflow configuration files (JSON format)
4. Required GitHub repository secrets configured

## ⚙️ Setup

### 1. Repository Secrets

Configure the following secrets in your GitHub repository (`Settings > Secrets and variables > Actions`):

#### Required for all platforms:
- `GITHUB_TOKEN` or `PAT` - GitHub Personal Access Token with workflow permissions
- `MINIO_ACCESS_KEY` - MinIO/S3 access key for data storage
- `MINIO_SECRET_KEY` - MinIO/S3 secret key for data storage

#### AWS Lambda specific:
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `AWS_DEFAULT_REGION` - AWS region (e.g., `us-east-1`)
- `AWS_LAMBDA_ROLE_ARN` - Lambda execution role ARN

#### OpenWhisk specific:
- `OW_API_KEY` - OpenWhisk API key in format `username:password`

### 2. Workflow Configuration Files

Create JSON configuration files in your repository root (examples: `project1.json`, `payload.json`). See [Configuration Files](#configuration-files) section for details.

## 🚀 Workflows

### Deploy Functions Workflow

**File:** `.github/workflows/deploy-functions.yml`

**Purpose:** Deploys FaaSr functions to specified cloud platforms based on your workflow configuration.

#### How to Run:

1. Go to your repository's **Actions** tab
2. Select **"Deploy FaaSr Functions"** workflow
3. Click **"Run workflow"**
4. Enter parameters:
   - **Workflow file name**: Name of your JSON configuration file (default: `project1.json`)
5. Click **"Run workflow"**

#### What it does:

- Reads your workflow configuration file
- Identifies target platforms (Lambda, GitHub Actions, OpenWhisk)
- Installs required dependencies and tools
- Deploys functions to each specified platform:
  - **AWS Lambda**: Creates/updates Lambda functions with container images
  - **GitHub Actions**: Creates workflow files in `.github/workflows/`
  - **OpenWhisk**: Creates/updates actions using the OpenWhisk CLI

#### Example Usage:
```
Workflow file: project1.json
```

### Trigger Function Workflow

**File:** `.github/workflows/trigger-function.yml`

**Purpose:** Executes a deployed FaaSr function with your workflow configuration.

#### How to Run:

1. Go to your repository's **Actions** tab
2. Select **"Trigger FaaSr Function"** workflow
3. Click **"Run workflow"**
4. Enter parameters:
   - **Workflow file name**: Name of your JSON configuration file (default: `payload.json`)
   - **Function name**: (Optional) Specific function to trigger
5. Click **"Run workflow"**

#### What it does:

- Reads your workflow configuration file
- Identifies the function to invoke (from `FunctionInvoke` field or parameter)
- Determines the target platform for the function
- Triggers the function execution:
  - **AWS Lambda**: Invokes Lambda function asynchronously
  - **GitHub Actions**: Triggers the deployed workflow via API
  - **OpenWhisk**: Invokes action via REST API

#### Example Usage:
```
Workflow file: payload.json
Function name: (leave empty to use FunctionInvoke from config)
```

## 📄 Configuration Files

### Basic Structure

Your JSON configuration files should follow this structure:

```json
{
    "ComputeServers": {
        "My_GitHub_Account": {
            "FaaSType": "GitHubActions",
            "UserName": "your-username",
            "ActionRepoName": "your-repo-name",
            "Branch": "main",
            "Token": "My_GitHub_Account_TOKEN"
        },
        "My_Lambda_Account": {
            "FaaSType": "Lambda",
            "Region": "us-east-1",
            "AccessKey": "My_Lambda_Account_ACCESS_KEY",
            "SecretKey": "My_Lambda_Account_SECRET_KEY"
        },
        "My_OW_Account": {
            "FaaSType": "OpenWhisk",
            "Endpoint": "your-openwhisk-host",
            "Namespace": "your-namespace",
            "SSL": "true",
            "API.key": "My_OW_Account_API_KEY"
        }
    },
    "DataStores": {
        "My_Minio_Bucket": {
            "Endpoint": "https://play.min.io",
            "Bucket": "your-bucket-name",
            "Region": "us-east-1",
            "Writable": "TRUE",
            "AccessKey": "My_Minio_Bucket_ACCESS_KEY",
            "SecretKey": "My_Minio_Bucket_SECRET_KEY"
        }
    },
    "FunctionList": {
        "function_name": {
            "FunctionName": "actual_function_name",
            "FaaSServer": "My_GitHub_Account",
            "Arguments": {
                "param1": "value1"
            },
            "InvokeNext": ["next_function"]
        }
    },
    "ActionContainers": {
        "function_name": "ghcr.io/faasr/github-actions-tidyverse"
    },
    "FunctionGitRepo": {
        "actual_function_name": "owner/repository"
    },
    "FunctionInvoke": "function_name",
    "LoggingDataStore": "My_Minio_Bucket",
    "DefaultDataStore": "My_Minio_Bucket"
}
```

### Key Fields Explained:

- **ComputeServers**: Define your cloud platforms and credentials
- **DataStores**: Configure data storage endpoints (MinIO, S3, etc.)
- **FunctionList**: Define your functions and their execution flow
- **ActionContainers**: Specify container images for each function
- **FunctionGitRepo**: Map functions to their source repositories
- **FunctionInvoke**: The entry point function for execution

### Credential Placeholders:

Use these placeholder patterns in your config files:
- `{ServerName}_TOKEN` for GitHub tokens
- `{ServerName}_ACCESS_KEY` and `{ServerName}_SECRET_KEY` for AWS/MinIO
- `{ServerName}_API_KEY` for OpenWhisk

The workflows will automatically replace these with actual values from your repository secrets.

## 💡 Usage Examples

### Example 1: Deploy to GitHub Actions only

1. Create `github-only.json`:
```json
{
    "ComputeServers": {
        "My_GitHub_Account": {
            "FaaSType": "GitHubActions",
            "UserName": "myusername",
            "ActionRepoName": "my-faasr-project",
            "Branch": "main",
            "Token": "My_GitHub_Account_TOKEN"
        }
    },
    "FunctionList": {
        "hello_world": {
            "FunctionName": "hello_function",
            "FaaSServer": "My_GitHub_Account"
        }
    },
    "ActionContainers": {
        "hello_world": "ghcr.io/faasr/github-actions-tidyverse"
    },
    "FunctionInvoke": "hello_world"
}
```

2. Run Deploy workflow with `github-only.json`
3. Run Trigger workflow with `github-only.json`

### Example 2: Multi-platform deployment

1. Create `multi-platform.json` with both GitHub Actions and AWS Lambda servers
2. Run Deploy workflow - functions will be deployed to both platforms
3. Run Trigger workflow - will execute on the platform specified by `FunctionInvoke`

## 🔧 Troubleshooting

### Common Issues:

1. **Missing secrets**: Ensure all required secrets are configured in your repository
2. **Invalid JSON**: Validate your configuration files using a JSON validator
3. **Permission errors**: Check that your tokens/keys have appropriate permissions
4. **Function not found**: Verify function names match between config and deployed functions

### Debug Information:

Both workflows provide detailed logging. Check the Actions logs for:
- Configuration file parsing
- Platform-specific deployment steps
- Function invocation responses
- Error messages and stack traces

### Getting Help:

1. Check the Actions logs for detailed error messages
2. Verify your configuration file structure
3. Ensure all required secrets are properly set
4. Test with a simple single-function workflow first

---

## 📚 Additional Resources

- [FaaSr Documentation](https://github.com/FaaSr)
- [FaaSr Turorial + JSON Workflow Builder](https://github.com/FaaSr/FaaSr-tutorial)

---

*This guide covers the essential usage of FaaSr CLI workflows. For advanced configurations and custom implementations, refer to the source code in the `scripts/` directory.*
