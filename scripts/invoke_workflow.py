#!/usr/bin/env python3

import argparse
import json
import os
import sys
import requests
import boto3
import subprocess



def parse_arguments():
    parser = argparse.ArgumentParser(description='Trigger FaaSr function from JSON file')
    parser.add_argument('--workflow-file', required=True,
                      help='Path to the workflow JSON file')
    return parser.parse_args()

def read_workflow_file(file_path):
    """Read and parse the workflow JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Workflow file {file_path} not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in workflow file {file_path}")
        sys.exit(1)

def get_credentials():
    """Get credentials from environment variables."""
    credentials = {
        "My_GitHub_Account_TOKEN": os.getenv('GITHUB_TOKEN'),
        "My_Minio_Bucket_ACCESS_KEY": os.getenv('MINIO_ACCESS_KEY'),
        "My_Minio_Bucket_SECRET_KEY": os.getenv('MINIO_SECRET_KEY'),
        "My_OW_Account_API_KEY": os.getenv('OW_API_KEY', ''),
        "My_Lambda_Account_ACCESS_KEY": os.getenv('AWS_ACCESS_KEY_ID', ''),
        "My_Lambda_Account_SECRET_KEY": os.getenv('AWS_SECRET_ACCESS_KEY', ''),
    }
    
    # Debug logging for MinIO credentials specifically
    print(f"Debug: MINIO_ACCESS_KEY environment variable: {'SET' if credentials['My_Minio_Bucket_ACCESS_KEY'] else 'NOT SET'}")
    print(f"Debug: MINIO_SECRET_KEY environment variable: {'SET' if credentials['My_Minio_Bucket_SECRET_KEY'] else 'NOT SET'}")
    
    return credentials

def build_faasr_payload(workflow_data, mask_secrets_for_github=False):
    # Start with credentials at the top (matching R deployment style)
    # payload = get_credentials().copy()

    # Add workflow data (excluding _workflow_file)
    workflow_copy = workflow_data.copy()
    if '_workflow_file' in workflow_copy:
        del workflow_copy['_workflow_file']
    # payload.update(workflow_copy)
    payload = workflow_copy
    
    # Get environment credentials
    credentials = get_credentials()
    
    # Replace placeholder values in ComputeServers with actual credentials based on FaaSType
    if 'ComputeServers' in payload:
        for server_key, server_config in payload['ComputeServers'].items():
            faas_type = server_config.get('FaaSType', '')
            
            if mask_secrets_for_github:
                # Mask secrets for GitHub Actions (existing logic)
                if faas_type.lower() in ['githubactions', 'github_actions', 'github']:
                    server_config['Token'] = f"{server_key}_TOKEN"
                elif faas_type.lower() in ['lambda', 'aws_lambda', 'aws']:
                    server_config['AccessKey'] = f"{server_key}_ACCESS_KEY"
                    server_config['SecretKey'] = f"{server_key}_SECRET_KEY"
                elif faas_type.lower() in ['openwhisk', 'open_whisk', 'ow']:
                    server_config['API.key'] = f"{server_key}_API_KEY"
            else:
                # Replace placeholder values with actual credentials
                if faas_type.lower() in ['lambda', 'aws_lambda', 'aws']:
                    # Replace Lambda AccessKey/SecretKey placeholders
                    if credentials['My_Lambda_Account_ACCESS_KEY']:
                        server_config['AccessKey'] = credentials['My_Lambda_Account_ACCESS_KEY']
                    if credentials['My_Lambda_Account_SECRET_KEY']:
                        server_config['SecretKey'] = credentials['My_Lambda_Account_SECRET_KEY']
                elif faas_type.lower() in ['githubactions', 'github_actions', 'github']:
                    if credentials['My_GitHub_Account_TOKEN']:
                        server_config['Token'] = credentials['My_GitHub_Account_TOKEN']
                elif faas_type.lower() in ['openwhisk', 'open_whisk', 'ow']:
                    # Always set the API.key field for OpenWhisk
                    if credentials['My_OW_Account_API_KEY']:
                        server_config['API.key'] = credentials['My_OW_Account_API_KEY']

    # Replace placeholder values in DataStores with actual credentials
    if 'DataStores' in payload:
        for store_key, store_config in payload['DataStores'].items():
            if mask_secrets_for_github:
                # Mask secrets for GitHub Actions (existing logic)
                store_config['AccessKey'] = f"{store_key}_ACCESS_KEY"
                store_config['SecretKey'] = f"{store_key}_SECRET_KEY"
            else:
                if store_key == 'My_Minio_Bucket':
                    print(f"Debug: Processing DataStore '{store_key}'")
                    print(f"Debug: Original AccessKey: {store_config.get('AccessKey', 'NOT SET')}")
                    print(f"Debug: Original SecretKey: {store_config.get('SecretKey', 'NOT SET')}")
                    
                    if credentials['My_Minio_Bucket_ACCESS_KEY']:
                        store_config['AccessKey'] = credentials['My_Minio_Bucket_ACCESS_KEY']
                        print(f"Debug: Replaced AccessKey with environment value")
                    else:
                        print(f"Debug: WARNING - MINIO_ACCESS_KEY not available from environment!")
                        
                    if credentials['My_Minio_Bucket_SECRET_KEY']:
                        store_config['SecretKey'] = credentials['My_Minio_Bucket_SECRET_KEY']
                        print(f"Debug: Replaced SecretKey with environment value")
                    else:
                        print(f"Debug: WARNING - MINIO_SECRET_KEY not available from environment!")
                    
                    print(f"Debug: Final AccessKey: {store_config.get('AccessKey', 'NOT SET')}")
                    print(f"Debug: Final SecretKey: {store_config.get('SecretKey', 'NOT SET')}")
    
    return payload

def trigger_github_actions(workflow_data, action_name):
    """Trigger a GitHub Actions workflow."""
    # Get action data
    action_data = workflow_data['ActionList'][action_name]
    server_name = action_data['FaaSServer']
    server_config = workflow_data['ComputeServers'][server_name]
    
    # Get GitHub credentials and repo info
    pat = get_github_token() # Use token from config or environment
    username = server_config['UserName']
    reponame = server_config['ActionRepoName']
    repo = f"{username}/{reponame}"
    git_ref = server_config.get('Branch', 'main')  # Default to 'main' if Branch not specified
    
    # Use workflow file naming logic with WorkflowName prefix
    workflow_name_prefix = workflow_data.get('WorkflowName', 'default')
    if not action_name.endswith(".yml") and not action_name.endswith(".yaml"):
        workflow_name = f"{workflow_name_prefix}-{action_name}.yml"
    else:
        workflow_name = f"{workflow_name_prefix}-{action_name}"

    # Create overwritten fields structure matching reference invoke_gh implementation
    # Start with basic workflow fields (excluding secrets initially)
    overwritten_fields = {
        "FunctionInvoke": action_name
    }
    
    # Add other workflow fields but exclude ComputeServers and DataStores initially
    for key, value in workflow_data.items():
        if key not in ["ComputeServers", "DataStores", "_workflow_file"]:
            overwritten_fields[key] = value
    
    # If UseSecretStore == False, include secrets in overwritten fields
    # If UseSecretStore == True, don't send secrets to next action
    if not server_config.get("UseSecretStore"):
        overwritten_fields["ComputeServers"] = workflow_data.get("ComputeServers", {})
        overwritten_fields["DataStores"] = workflow_data.get("DataStores", {})

    # Ensure we have valid JSON content
    if not overwritten_fields:
        overwritten_fields = {}
    
    json_overwritten = json.dumps(overwritten_fields)

    # Create payload URL following the structure: {username}/{repo}/{branch}/{workflow_file}
    # Extract workflow file name from the stored path
    workflow_file_path = workflow_data.get('_workflow_file', '')
    workflow_filename = os.path.basename(workflow_file_path)
    payload_url = f"{username}/{reponame}/{git_ref}/{workflow_filename}"
    print(f"Debug: PAYLOAD_URL: {payload_url}")
    
    # Create inputs similar to invoke_gh method
    inputs = {
        "OVERWRITTEN": json_overwritten,
        "PAYLOAD_URL": payload_url,
    }
    
    # Create URL for GitHub API
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_name}/dispatches"
    
    # Create headers for POST request
    headers = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    # Create body for POST request
    body = {
        "ref": git_ref,
        "inputs": {
            "OVERWRITTEN": json_overwritten,
            "PAYLOAD_URL": payload_url
        }
    }
    
    print(f"Debug: Request URL: {url}")
    print(f"Debug: Request Body: {body}")
    # Send request
    try:
        response = requests.post(url, headers=headers, json=body)
        
        # Enhanced error handling based on invoke_gh method
        if response.status_code == 204:
            print(f"✓ Successfully triggered GitHub Actions workflow: {workflow_name}")
        elif response.status_code == 401:
            print("✗ GitHub Action: Authentication failed, check the credentials")
            sys.exit(1)
        elif response.status_code == 404:
            print(f"✗ GitHub Action: Cannot find the destination: "
                  f"check repo: {repo}, workflow: {workflow_name}, "
                  f"and branch: {git_ref}")
            sys.exit(1)
        elif response.status_code == 422:
            try:
                message = response.json().get("message")
                if message:
                    print(f"✗ GitHub Action: {message}")
                else:
                    print(f"✗ GitHub Action: Cannot find the destination; check ref {git_ref}")
            except json.JSONDecodeError:
                print(f"✗ GitHub Action: Cannot find the destination; check ref {git_ref}")
            sys.exit(1)
        else:
            try:
                if response.text:
                    response_data = response.json()
                    message = response_data.get("message")
                    if message:
                        print(f"✗ GitHub Action: {message}")
                    else:
                        print("✗ GitHub Action: Unknown error happens when invoke next function")
                else:
                    print("✗ GitHub Action: No response from GitHub")
            except json.JSONDecodeError:
                print(f"✗ GitHub Action: Error {response.status_code} - {response.text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"✗ Error triggering GitHub Actions workflow: {str(e)}")
        sys.exit(1)



def get_github_token():
    # Get GitHub PAT from environment variable
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        sys.exit(1)
    return token

def trigger_lambda(workflow_data, action_name):
    """Trigger an AWS Lambda function."""
    # Get action data
    action_data = workflow_data['ActionList'][action_name]
    server_name = action_data['FaaSServer']
    server_config = workflow_data['ComputeServers'][server_name]
    
    # Get AWS credentials from environment variables (same as deploy script)
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = server_config.get('Region', 'us-east-1')
    
    # Use WorkflowName prefix with action name for Lambda function name
    workflow_name_prefix = workflow_data.get('WorkflowName', 'default')
    lambda_function_name = f"{workflow_name_prefix}-{action_name}"
    
    # Create payload with credentials
    payload = build_faasr_payload(workflow_data)
    
    # Create Lambda client
    try:
        lambda_client = boto3.client(
            'lambda',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
    except Exception as e:
        print(f"Error creating Lambda client: {str(e)}")
        sys.exit(1)
    
    # Invoke function synchronously
    try:
        print(f"Debug: Invoking Lambda function synchronously: {lambda_function_name}")
        
        # Asynchronous invocation (commented out)
        response = lambda_client.invoke(
            FunctionName=lambda_function_name,
            InvocationType='Event',  # Asynchronous invocation
            Payload=json.dumps(payload)
        )
        if response['StatusCode'] == 202:
            print(f"✓ Successfully triggered Lambda function: {lambda_function_name}")
            print("Function is running asynchronously - check CloudWatch logs for execution details")
        
        # Synchronous invocation
        # response = lambda_client.invoke(
        #     FunctionName=lambda_function_name,
        #     InvocationType='RequestResponse',  # Synchronous invocation
        #     Payload=json.dumps(payload)
        # )
        
        # print(f"Debug: Lambda response status: {response.get('StatusCode')}")
        
        # For synchronous invocations, check status and handle errors
        if response['StatusCode'] == 200:
            # Check if there was a function error
            if 'FunctionError' in response:
                error_type = response['FunctionError']
                payload_response = json.loads(response['Payload'].read())
                print(f"Lambda function error ({error_type}): {payload_response}")
                sys.exit(1)
            else:
                print(f"✓ Successfully executed Lambda function: {lambda_function_name}")
                # Print the response payload
                payload_response = response['Payload'].read()
                if payload_response:
                    response_text = payload_response.decode('utf-8')
                    print(f"Function response: {response_text}")
                else:
                    print("Function completed successfully (no response payload)")
        else:
            print(f"✗ Lambda function invocation failed with status: {response['StatusCode']}")
            if 'Payload' in response:
                payload_content = response['Payload'].read()
                if payload_content:
                    print(f"Response payload: {payload_content.decode('utf-8')}")
            sys.exit(1)
            
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"✗ Error: Lambda function '{lambda_function_name}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error triggering Lambda function: {str(e)}")
        sys.exit(1)

def trigger_openwhisk(workflow_data, action_name):
    """Trigger an OpenWhisk action."""
    # Get action data
    action_data = workflow_data['ActionList'][action_name]
    server_name = action_data['FaaSServer']
    server_config = workflow_data['ComputeServers'][server_name]
    
    # Get OpenWhisk credentials from server config
    endpoint = server_config['Endpoint']
    namespace = server_config['Namespace']
    ssl = server_config['SSL'].lower() == 'true'
    
    # Get API key and split it
    ow_api_key = os.getenv('OW_API_KEY')
    if not ow_api_key:
        print("Error: OW_API_KEY environment variable not set")
        sys.exit(1)
    
    api_key_parts = ow_api_key.split(':')
    if len(api_key_parts) != 2:
        print("Error: OW_API_KEY should be in format 'username:password'")
        sys.exit(1)
    
    # Add protocol to endpoint if not present
    # Force HTTPS since the server seems to require it regardless of SSL setting
    if not endpoint.startswith(('http://', 'https://')):
        endpoint = 'https://' + endpoint
    elif endpoint.startswith('http://'):
        # Convert http to https if server requires it
        endpoint = endpoint.replace('http://', 'https://')
    
    # Use WorkflowName prefix with action name for OpenWhisk action name
    workflow_name_prefix = workflow_data.get('WorkflowName', 'default')
    openwhisk_action_name = f"{workflow_name_prefix}-{action_name}"
    
    url = f"{endpoint}/api/v1/namespaces/{namespace}/actions/{openwhisk_action_name}?blocking=false&result=false"
    
  
    payload = build_faasr_payload(workflow_data)
    
    # Debug: print the payload being sent to OpenWhisk
    print("\n===== OpenWhisk Payload Debug =====")
    print(json.dumps(payload, indent=2))
    print("===== End Payload Debug =====\n")
    
    # Set headers
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    try:
        print(f"Invoking OpenWhisk action: {openwhisk_action_name}")
        print(f"Debug: Using namespace: {namespace}")
        print(f"Debug: URL: {url}")
        
        response = requests.post(
            url=url,
            auth=(api_key_parts[0], api_key_parts[1]),  # HTTP Basic Auth
            headers=headers,
            json=payload,
            verify=ssl  # SSL verification based on config
        )
        
        if response.status_code in [200, 202]:
            print(f"✓ Successfully invoked OpenWhisk action: {openwhisk_action_name}")
            if response.text:
                print(f"Response: {response.text}")
        else:
            print(f"✗ Error invoking OpenWhisk action: {response.status_code} - {response.text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"✗ Error triggering OpenWhisk action: {str(e)}")
        sys.exit(1)

def main():
    args = parse_arguments()
    workflow_data = read_workflow_file(args.workflow_file)
    
    # Store the workflow file path
    workflow_data['_workflow_file'] = args.workflow_file
    
    # Get the function to invoke
    function_invoke = workflow_data.get('FunctionInvoke')
    if not function_invoke:
        print("Error: No FunctionInvoke specified in workflow file")
        sys.exit(1)
    
    if function_invoke not in workflow_data['ActionList']:
        print(f"Error: FunctionInvoke '{function_invoke}' not found in ActionList")
        sys.exit(1)
    
    # Get action data
    action_data = workflow_data['ActionList'][function_invoke]
    server_name = action_data['FaaSServer']
    server_config = workflow_data['ComputeServers'][server_name]
    faas_type = server_config['FaaSType'].lower()
    
    print(f"Triggering action '{function_invoke}' on {faas_type}...")
    
    # Trigger based on FaaS type
    if faas_type in ['githubactions', 'github_actions', 'github']:
        trigger_github_actions(workflow_data, function_invoke)
    elif faas_type in ['lambda', 'aws_lambda', 'aws']:
        trigger_lambda(workflow_data, function_invoke)
    elif faas_type in ['openwhisk', 'open_whisk', 'ow']:
        trigger_openwhisk(workflow_data, function_invoke)
    else:
        print(f"Error: Unsupported FaaS type: {faas_type}")
        sys.exit(1)
    
    print("Action trigger completed successfully!")

if __name__ == '__main__':
    main() 