"""
AgentOrchestrator Lambda Handler
Main entry point for the AccessAgent autonomous agent system
"""

import json
import logging
import os
import uuid
import boto3
import urllib.request
from datetime import datetime
from bedrock_agent import BedrockAgent

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "accessagent-projects")
table = dynamodb.Table(DYNAMODB_TABLE)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
}


def update_progress(project_id, status, current_step, progress, activity_log_entry=None, **kwargs):
    """
    Update project progress in DynamoDB
    """
    try:
        update_expr_parts = [
            "#status = :status",
            "current_step = :current_step",
            "progress = :progress",
            "updated_at = :timestamp"
        ]
        expr_attr_names = {"#status": "status"}
        expr_attr_values = {
            ":status": status,
            ":current_step": current_step,
            ":progress": progress,
            ":timestamp": datetime.utcnow().isoformat()
        }
        
        for key, value in kwargs.items():
            update_expr_parts.append(f"{key} = :{key}")
            expr_attr_values[f":{key}"] = value
        
        if activity_log_entry:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "message": activity_log_entry,
                "step": current_step
            }
            update_expr_parts.append("activity_log = list_append(if_not_exists(activity_log, :empty_list), :log)")
            expr_attr_values[":log"] = [log_entry]
            expr_attr_values[":empty_list"] = []
        
        table.update_item(
            Key={"project_id": project_id},
            UpdateExpression="SET " + ", ".join(update_expr_parts),
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values
        )
        logger.info(f"Progress updated for {project_id}: {current_step} ({progress}%)")
    except Exception as e:
        logger.error(f"Error updating progress: {e}")


def handle_async_processing(event, context):
    """
    Handle async agent processing (invoked by Lambda itself)
    """
    try:
        project_id = event.get("project_id")
        site_url = event.get("site_url")
        repo_url = event.get("repo_url")
        
        logger.info(f"Starting AgentCore processing for project {project_id}")
        update_progress(project_id, "scanning", "Initializing scan", 10, "Starting accessibility scan...")
        
        agent = BedrockAgent(region=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        
        results = agent.run_autonomous_loop(
            site_url=site_url,
            repo_url=repo_url,
            project_id=project_id,
            progress_callback=lambda step, progress, msg: update_progress(project_id, "processing", step, progress, msg)
        )
        
        # Extract framework info if available
        framework = None
        for step in results.get("steps", []):
            if step.get("step") == "generate_patch":
                framework = step.get("result", {}).get("framework")
                break
        
        update_expression = "SET agent_results = :results, updated_at = :timestamp"
        attr_values = {
            ":results": json.dumps(results, default=str),
            ":timestamp": datetime.utcnow().isoformat()
        }
        
        if framework:
            update_expression += ", framework = :framework"
            attr_values[":framework"] = framework
        
        table.update_item(
            Key={"project_id": project_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=attr_values
        )
        
        logger.info(f"Agent loop completed for project {project_id}: status={results.get('status')}")
        return {"statusCode": 200, "message": "Processing complete"}
        
    except Exception as e:
        logger.error(f"Error in async processing: {str(e)}", exc_info=True)
        try:
            update_progress(
                event.get("project_id"),
                "error",
                "Error occurred",
                0,
                f"Error: {str(e)}",
                error=str(e)
            )
        except:
            pass
        return {"statusCode": 500, "error": str(e)}


def handle_get_repos(event):
    """
    Handle GET request to fetch GitHub repositories
    """
    try:
        # Fetch GitHub token from Secrets Manager
        secret_name = os.environ.get("GITHUB_TOKEN_SECRET_NAME")
        if not secret_name:
            return {
                "statusCode": 500,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "GitHub token secret not configured"})
            }
        
        secrets_client = boto3.client("secretsmanager")
        secret_response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_data = json.loads(secret_response["SecretString"])
        github_token = secret_data.get("token", "")
        
        # Fetch repos from GitHub API with pagination
        all_repos = []
        page = 1
        per_page = 100
        
        while True:
            req = urllib.request.Request(
                f"https://api.github.com/user/repos?sort=updated&per_page={per_page}&page={page}",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "AccessAgent"
                }
            )
            
            with urllib.request.urlopen(req) as response:
                repos = json.loads(response.read().decode('utf-8'))
                
            if not repos:
                break
                
            all_repos.extend(repos)
            
            # Stop after 3 pages (300 repos) to avoid timeout
            if page >= 3 or len(repos) < per_page:
                break
                
            page += 1
            
        # Return simplified repo data
        simplified_repos = [
            {
                "id": repo["id"],
                "name": repo["name"],
                "full_name": repo["full_name"],
                "html_url": repo["html_url"],
                "description": repo.get("description")
            }
            for repo in all_repos
        ]
        
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(simplified_repos)
        }
    except urllib.error.HTTPError as e:
        logger.error(f"GitHub API error: {e.code} - {e.read().decode('utf-8')}")
        return {
            "statusCode": e.code,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": f"GitHub API error: {e.code}"})
        }
    except Exception as e:
        logger.error(f"Error fetching repos: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": str(e)})
        }


def lambda_handler(event, context):
    """
    Main Lambda handler for agent orchestration
    Handles both POST (start new scan) and GET (retrieve project status/repos)
    """
    logger.info(f"Agent Orchestrator invoked with event: {json.dumps(event)[:500]}")
    
    # Check if this is an async processing invocation
    if event.get("action") == "process_agent":
        return handle_async_processing(event, context)
    
    try:
        http_method = event.get("httpMethod", "POST")
        path = event.get("path", "")
        
        if http_method == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": CORS_HEADERS,
                "body": json.dumps({"message": "OK"})
            }
        elif http_method == "GET":
            # Check path to determine which handler to use
            if "/repos" in path:
                return handle_get_repos(event)
            else:
                return handle_get_project(event)
        elif http_method == "POST":
            return handle_start_scan(event, context)
        else:
            return {
                "statusCode": 405,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Method not allowed"})
            }
            
    except Exception as e:
        logger.error(f"Error in agent orchestrator: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": str(e), "type": type(e).__name__})
        }


def handle_get_project(event):
    """
    Handle GET request to retrieve project status
    """
    try:
        path_params = event.get("pathParameters", {})
        project_id = path_params.get("project_id")
        
        if not project_id:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "project_id is required"})
            }
        
        response = table.get_item(Key={"project_id": project_id})
        
        if "Item" not in response:
            return {
                "statusCode": 404,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Project not found"})
            }
        
        # Parse agent_results and extract issues for frontend
        item = response["Item"]
        if "agent_results" in item:
            try:
                agent_results = json.loads(item["agent_results"]) if isinstance(item["agent_results"], str) else item["agent_results"]
                
                # Extract issues from scan step
                for step in agent_results.get("steps", []):
                    if step.get("step") == "scan":
                        scan_result = step.get("result", {})
                        if "body" in scan_result:
                            scan_body = json.loads(scan_result["body"]) if isinstance(scan_result["body"], str) else scan_result["body"]
                            item["issues"] = scan_body.get("issues", [])
                            item["initial_score"] = scan_body.get("score", 0)
                        break
                
                # Extract PR URL and improvement data
                item["pr_url"] = agent_results.get("pr_url")
                item["improvement"] = agent_results.get("improvement", {})
                
            except Exception as e:
                logger.warning(f"Could not parse agent_results: {e}")
        
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(item, default=str)
        }
        
    except Exception as e:
        logger.error(f"Error retrieving project: {str(e)}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": str(e)})
        }


def handle_start_scan(event, context):
    """
    Handle POST request to start new accessibility scan
    Initiates the AgentCore autonomous loop ASYNCHRONOUSLY
    """
    try:
        body = json.loads(event.get("body", "{}"))
        site_url = body.get("site_url")
        repo_url = body.get("repo_url")
        
        if not site_url or not repo_url:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "site_url and repo_url are required"})
            }
        
        if not site_url.startswith("http"):
            site_url = f"https://{site_url}"
        
        if not repo_url.startswith("https://github.com"):
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "repo_url must be a valid GitHub repository URL"})
            }
        
        project_id = str(uuid.uuid4())
        
        table.put_item(
            Item={
                "project_id": project_id,
                "site_url": site_url,
                "repo_url": repo_url,
                "status": "processing",
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"Created project {project_id}, starting async processing")
        
        # Invoke this Lambda asynchronously to process in background
        lambda_client = boto3.client("lambda")
        lambda_client.invoke(
            FunctionName=context.function_name,
            InvocationType="Event",  # Async invocation
            Payload=json.dumps({
                "action": "process_agent",
                "project_id": project_id,
                "site_url": site_url,
                "repo_url": repo_url
            })
        )
        
        response_body = {
            "project_id": project_id,
            "status": "processing",
            "message": "Agent started processing. Use GET /projects/{project_id} to check status."
        }
        
        logger.info(f"Agent processing started asynchronously for project {project_id}")
        
        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(response_body)
        }
        
    except Exception as e:
        logger.error(f"Error starting scan: {str(e)}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": str(e)})
        }
