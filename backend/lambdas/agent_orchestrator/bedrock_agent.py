"""
Bedrock AgentCore integration
Implements autonomous reasoning loop with custom primitives
"""

import os
import json
import boto3
import logging
from typing import Dict, List, Any, Optional
from tools import TOOLS, get_tool_by_name
from prompts import AGENT_SYSTEM_PROMPT, REASONING_PROMPT, PATCH_GENERATION_PROMPT, VERIFICATION_PROMPT

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class BedrockAgent:
    """
    AgentCore implementation using Claude 3.5 Sonnet
    Orchestrates the autonomous accessibility fixing workflow
    """
    
    def __init__(self, region: str = "us-east-1"):
        self.bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)
        self.lambda_client = boto3.client("lambda", region_name=region)
        # Use inference profile for Claude Sonnet 4.5
        self.model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        self.conversation_history = []
        
    def invoke_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Primitive: Invoke Lambda function corresponding to tool
        This is the core AgentCore primitive for tool execution
        """
        logger.info(f"Invoking tool: {tool_name} with input: {json.dumps(tool_input)}")
        
        function_name_map = {
            "scan_site": "accessagent-scan"
        }
        
        function_name = function_name_map.get(tool_name)
        if not function_name:
            return {"error": f"Unknown tool: {tool_name}"}
        
        try:
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(tool_input)
            )
            
            result = json.loads(response["Payload"].read())
            logger.info(f"Tool {tool_name} result: {json.dumps(result)[:500]}")
            return result
            
        except Exception as e:
            logger.error(f"Error invoking tool {tool_name}: {str(e)}", exc_info=True)
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"error": str(e)}
    
    def _get_github_token(self) -> str:
        """Get GitHub token from Secrets Manager"""
        try:
            import boto3
            secrets_client = boto3.client('secretsmanager')
            response = secrets_client.get_secret_value(SecretId='accessagent/github-token')
            secret_string = response['SecretString']
            
            # Parse JSON if it's stored as {"token": "..."}
            try:
                secret_data = json.loads(secret_string)
                return secret_data.get('token', secret_string)
            except json.JSONDecodeError:
                return secret_string
        except Exception as e:
            logger.warning(f"Could not fetch GitHub token: {e}")
            return ""
    
    def _fetch_file_tree(self, owner: str, repo: str, path: str = "") -> List[Dict[str, Any]]:
        """Recursively fetch file tree from GitHub"""
        import urllib.request
        try:
            api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
            headers = {'User-Agent': 'AccessAgent-Agent'}
            
            # Add GitHub token if available
            github_token = self._get_github_token()
            if github_token:
                headers['Authorization'] = f'token {github_token}'
            
            req = urllib.request.Request(api_url, headers=headers)
            
            with urllib.request.urlopen(req) as response:
                contents = json.loads(response.read())
            
            files = []
            for item in contents:
                if item['type'] == 'file' and (
                    item['name'].endswith(('.html', '.jsx', '.tsx', '.vue', '.svelte', '.js', '.ts', '.css'))
                ):
                    files.append({
                        'path': item['path'],
                        'name': item['name'],
                        'type': item['type'],
                        'size': item['size']
                    })
                elif item['type'] == 'dir' and item['name'] not in ['.git', 'node_modules', '.next', 'dist', 'build']:
                    # Recursively fetch subdirectories (max depth 3)
                    if path.count('/') < 3:
                        try:
                            subfiles = self._fetch_file_tree(owner, repo, item['path'])
                            files.extend(subfiles)
                        except:
                            pass
            
            return files
        except Exception as e:
            logger.warning(f"Could not fetch directory {path}: {e}")
            return []
    
    def _get_repo_structure(self, repo_url: str) -> Dict[str, Any]:
        """Fetch repository structure and detect framework type"""
        try:
            import urllib.request
            parts = repo_url.rstrip('/').split('/')
            owner, repo = parts[-2], parts[-1]
            
            result = {
                "framework": "html",
                "files": [],
                "structure": "",
                "package_json": None
            }
            
            # Check for package.json to detect JS framework
            try:
                package_url = f"https://api.github.com/repos/{owner}/{repo}/contents/package.json"
                headers = {'User-Agent': 'AccessAgent-Agent'}
                
                # Add GitHub token if available
                github_token = self._get_github_token()
                if github_token:
                    headers['Authorization'] = f'token {github_token}'
                
                req = urllib.request.Request(package_url, headers=headers)
                with urllib.request.urlopen(req) as response:
                    package_data = json.loads(response.read())
                    if package_data.get('encoding') == 'base64':
                        import base64
                        package_content = base64.b64decode(package_data['content']).decode('utf-8')
                        result["package_json"] = json.loads(package_content)
                        
                        # Detect framework from dependencies
                        deps = result["package_json"].get("dependencies", {})
                        dev_deps = result["package_json"].get("devDependencies", {})
                        all_deps = {**deps, **dev_deps}
                        
                        if "next" in all_deps:
                            result["framework"] = "nextjs"
                        elif "react" in all_deps:
                            result["framework"] = "react"
                        elif "vue" in all_deps:
                            result["framework"] = "vue"
                        elif "@angular/core" in all_deps:
                            result["framework"] = "angular"
                        elif "svelte" in all_deps:
                            result["framework"] = "svelte"
            except Exception as e:
                logger.info(f"No package.json found, assuming HTML: {e}")
            
            # Fetch complete file tree
            all_files = self._fetch_file_tree(owner, repo)
            result["files"] = [f['path'] for f in all_files]
            
            # Categorize files
            component_files = [f['path'] for f in all_files if any(dir in f['path'] for dir in ['components/', 'app/', 'pages/', 'src/'])]
            style_files = [f['path'] for f in all_files if f['path'].endswith('.css')]
            
            # Build structure description
            if result["framework"] == "nextjs":
                result["structure"] = f"Next.js project. Component files: {', '.join(component_files[:10])}"
            elif result["framework"] in ["react", "vue", "angular", "svelte"]:
                result["structure"] = f"{result['framework'].title()} project. Component files: {', '.join(component_files[:10])}"
            else:
                html_files = [f['path'] for f in all_files if f['path'].endswith('.html')]
                result["structure"] = f"Plain HTML. Files: {', '.join(html_files)}"
            
            logger.info(f"Detected framework: {result['framework']}, structure: {result['structure']}")
            return result
            
        except Exception as e:
            logger.warning(f"Could not fetch repo structure: {e}")
            return {
                "framework": "html",
                "files": [],
                "structure": "Repository structure unknown. Will attempt to fix common accessibility issues.",
                "package_json": None
            }
    
    def _generate_patch_locally(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate complete file contents using Bedrock reasoning
        Fetches actual file contents and asks AI to generate corrected versions
        """
        issues = tool_input.get("issues", [])
        repo_url = tool_input.get("repo_url", "")
        
        # Get actual repository structure and framework
        repo_info = self._get_repo_structure(repo_url)
        framework = repo_info.get("framework", "html")
        structure = repo_info.get("structure", "Unknown structure")
        files = repo_info.get("files", [])
        
        logger.info(f"Repository framework: {framework}, structure: {structure}")
        
        # Fetch actual file contents from GitHub
        owner, repo = repo_url.replace("https://github.com/", "").split("/")[:2]
        github_token = self._get_github_token()
        
        file_contents = {}
        
        # Smart file selection based on issues and framework
        # 1. Extract file paths mentioned in issues (selectors often contain filenames)
        files_mentioned_in_issues = set()
        for issue in issues[:20]:  # Check top 20 issues
            selector = issue.get('selector', '')
            # Try to infer component names from selectors
            if '.' in selector or '#' in selector:
                # Extract potential component/class names that might map to files
                parts = selector.replace('.', ' ').replace('#', ' ').split()
                for part in parts:
                    if part and len(part) > 2:
                        files_mentioned_in_issues.add(part)
        
        # 2. Priority patterns based on framework
        if framework == "nextjs":
            priority_patterns = ['app/page.tsx', 'app/layout.tsx', 'app/globals.css', 'components/', 'app/']
        elif framework == "react":
            priority_patterns = ['App.tsx', 'App.jsx', 'index.tsx', 'index.jsx', 'components/', 'src/']
        else:
            priority_patterns = ['index.html', 'main.css', 'style.css', 'app.js']
        
        # 3. Find matching files (prioritize smaller files for better context)
        candidate_files = []
        for file_path in files:
            # Check if file matches priority patterns or issue mentions
            priority_score = 0
            for pattern in priority_patterns:
                if pattern in file_path:
                    priority_score += 10
            
            # Boost score if filename contains words from issues
            file_name = file_path.split('/')[-1].lower()
            for mentioned in files_mentioned_in_issues:
                if mentioned.lower() in file_name:
                    priority_score += 5
            
            if priority_score > 0:
                candidate_files.append((file_path, priority_score))
        
        # Sort by priority and fetch top files
        candidate_files.sort(key=lambda x: x[1], reverse=True)
        web_files = [f[0] for f in candidate_files[:10]]  # Fetch top 10 files
        
        logger.info(f"Prioritized files to fetch: {web_files}")
        
        for file_path in web_files:
            try:
                import requests
                response = requests.get(
                    f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}",
                    headers={"Authorization": f"token {github_token}"},
                    params={"ref": "main"}
                )
                if response.status_code == 200:
                    import base64
                    content = base64.b64decode(response.json()["content"]).decode("utf-8")
                    # Include files up to 5000 chars for better context
                    if len(content) < 5000:
                        file_contents[file_path] = content
                        logger.info(f"Fetched {file_path} ({len(content)} chars)")
                    else:
                        # For large files, include first 4000 chars with a note
                        file_contents[file_path] = content[:4000] + "\n\n// ... (file truncated for context)"
                        logger.info(f"Fetched {file_path} (truncated from {len(content)} chars)")
            except Exception as e:
                logger.warning(f"Could not fetch {file_path}: {e}")
        
        logger.info(f"Fetched {len(file_contents)} file contents for AI analysis")
        
        # Format repo context with complete file contents
        files_info = "\n\n".join([
            f"**File: {path}**\n```{path.split('.')[-1]}\n{content}\n```" 
            for path, content in file_contents.items()
        ])
        
        # Create detailed issue descriptions with context
        issues_detailed = []
        for issue in issues[:15]:  # Top 15 most critical issues
            issues_detailed.append({
                "rule": issue.get("rule", "unknown"),
                "description": issue.get("description", ""),
                "impact": issue.get("impact", "moderate"),
                "selector": issue.get("selector", ""),
                "help": issue.get("help", ""),
                "helpUrl": issue.get("helpUrl", ""),
                "wcag": issue.get("wcag", [])
            })
        
        repo_context = f"""**Repository Information:**
- URL: {repo_url}
- Framework: {framework.upper()}
- Structure: {structure}

**Files Analyzed (showing {len(file_contents)} of {len(files)} total files):**
{files_info}"""
        
        prompt = PATCH_GENERATION_PROMPT.replace(
            "{repo_url}", repo_context
        ).replace(
            "{prioritized_issues}", json.dumps(issues_detailed, indent=2)
        )
        
        # Use higher token limit for complete file generation
        response = self._invoke_bedrock(prompt, max_tokens=16000, temperature=0.1)  # Lower temp for more precise code
        
        # Log the response for debugging
        logger.info(f"Bedrock patch response (first 1000 chars): {response[:1000]}")
        
        try:
            patches = self._extract_patches_from_response(response)
            logger.info(f"Extracted {len(patches)} patches")
            return {
                "patches": patches,
                "reasoning": response[:500]
            }
        except Exception as e:
            logger.error(f"Error parsing patches: {str(e)}")
            logger.error(f"Full response: {response[:2000]}")
            return {
                "patches": [],
                "error": str(e),
                "raw_response": response[:1000]
            }
    
    def _extract_patches_from_response(self, response: str) -> List[Dict[str, str]]:
        """Extract complete file contents from LLM response"""
        patches = []
        import re
        
        logger.info(f"Extracting file contents from response of length: {len(response)}")
        
        # Try to extract JSON array with complete file contents
        try:
            # Look for JSON code blocks first
            json_code_blocks = re.findall(r'```json\n(.*?)```', response, re.DOTALL)
            for json_str in json_code_blocks:
                try:
                    patches_json = json.loads(json_str)
                    if isinstance(patches_json, list) and len(patches_json) > 0:
                        # Validate it has the expected format (file_path and content)
                        if all('file_path' in p and 'content' in p for p in patches_json):
                            logger.info(f"Found {len(patches_json)} complete files in JSON code block")
                            return patches_json
                except Exception as e:
                    logger.debug(f"Failed to parse JSON block: {e}")
                    continue
            
            # Try to find JSON array directly in response
            json_array_match = re.search(r'\[\s*\{[^}]*"file_path"[^}]*"content"[^\]]*\]', response, re.DOTALL)
            if json_array_match:
                try:
                    patches_json = json.loads(json_array_match.group())
                    if isinstance(patches_json, list) and len(patches_json) > 0:
                        logger.info(f"Found {len(patches_json)} complete files in JSON array")
                        return patches_json
                except Exception as e:
                    logger.debug(f"Failed to parse JSON array: {e}")
        except Exception as e:
            logger.info(f"No valid JSON found: {str(e)[:100]}")
        
        # If no valid patches found, log the response for debugging
        if not patches:
            logger.warning("No complete files extracted from response")
            logger.info(f"Response preview (first 1000 chars): {response[:1000]}")
            # Don't return mock patches - let Fargate handle it
            return []
        
        logger.info(f"Returning {len(patches)} complete file contents")
        return patches
    
    def reason(self, context: Dict[str, Any]) -> str:
        """
        Reasoning primitive: Analyze situation and determine next action
        Core of AgentCore's autonomous decision-making
        """
        issues = context.get("issues", [])
        issue_count = len(issues)
        
        issues_summary = "\n".join([
            f"- {issue.get('rule', 'unknown')}: {issue.get('description', '')} "
            f"(severity: {issue.get('severity', 'unknown')}, count: {issue.get('count', 1)})"
            for issue in issues[:10]
        ])
        
        prompt = REASONING_PROMPT.format(
            issue_count=issue_count,
            issues_summary=issues_summary
        )
        
        reasoning = self._invoke_bedrock(prompt, max_tokens=2000)
        logger.info(f"Agent reasoning: {reasoning[:300]}")
        
        return reasoning
    
    def _invoke_bedrock(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.3) -> str:
        """
        Core Bedrock invocation with prompt caching and exponential backoff with jitter
        Uses prompt caching to reduce latency and avoid throttling
        """
        import time
        import random
        
        # Use prompt caching for system prompt (reduces latency & cost)
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": [
                {
                    "type": "text",
                    "text": AGENT_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"}
                }
            ],
            "messages": messages
        }
        
        max_retries = 4
        base_delay = 3
        
        for attempt in range(max_retries):
            try:
                response = self.bedrock_runtime.invoke_model(
                    modelId=self.model_id,
                    body=json.dumps(request_body)
                )
                
                response_body = json.loads(response["body"].read())
                content = response_body.get("content", [])
                
                if content and len(content) > 0:
                    return content[0].get("text", "")
                
                return ""
                
            except Exception as e:
                error_msg = str(e)
                if "ThrottlingException" in error_msg or "Too many requests" in error_msg:
                    if attempt < max_retries - 1:
                        # Exponential backoff with jitter
                        delay = base_delay * (2 ** attempt)
                        jitter = random.uniform(0, delay * 0.3)  # Add 0-30% jitter
                        total_delay = delay + jitter
                        logger.warning(f"Bedrock throttled, retrying in {total_delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(total_delay)
                        continue
                logger.error(f"Error invoking Bedrock: {error_msg}")
                return f"Error: {error_msg}"
        
        return "Error: Max retries exceeded"
    
    def _trigger_fargate_agent(self, project_id: str) -> Dict[str, Any]:
        """
        Trigger Fargate task to handle build-verify-push workflow
        """
        try:
            import boto3
            ecs = boto3.client('ecs')
            
            cluster = os.environ.get('ECS_CLUSTER')
            task_definition = os.environ.get('ECS_TASK_DEFINITION')
            security_group = os.environ.get('ECS_SECURITY_GROUP')
            
            if not cluster or not task_definition or not security_group:
                logger.warning("ECS configuration not found, skipping Fargate")
                return {"success": False, "error": "Fargate not configured"}
            
            # IDEMPOTENCY: Check if task already running for this project
            try:
                running_tasks = ecs.list_tasks(
                    cluster=cluster,
                    desiredStatus='RUNNING'
                )
                
                for task_arn in running_tasks.get('taskArns', []):
                    task_details = ecs.describe_tasks(cluster=cluster, tasks=[task_arn])
                    for task in task_details.get('tasks', []):
                        # Check if any running task has this project_id
                        for override in task.get('overrides', {}).get('containerOverrides', []):
                            for env in override.get('environment', []):
                                if env['name'] == 'PROJECT_ID' and env['value'] == project_id:
                                    logger.info(f"Task already running for project {project_id}, skipping duplicate")
                                    return {"success": True, "task_arn": task_arn, "note": "Task already running"}
            except Exception as e:
                logger.warning(f"Could not check for duplicate tasks: {e}")
            
            # Get VPC and subnets
            ec2 = boto3.client('ec2')
            
            # Find any VPC with tag aws:cloudformation:stack-name containing "AccessAgent"
            vpcs_response = ec2.describe_vpcs(
                Filters=[
                    {'Name': 'tag:aws:cloudformation:stack-name', 'Values': ['*AccessAgent*']}
                ]
            )
            
            if not vpcs_response['Vpcs']:
                # Fallback: get all VPCs and use first one
                vpcs_response = ec2.describe_vpcs()
            
            vpc_id = vpcs_response['Vpcs'][0]['VpcId']
            logger.info(f"Using VPC: {vpc_id}")
            
            # Get public subnets (have MapPublicIpOnLaunch = True)
            public_subnets_response = ec2.describe_subnets(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'map-public-ip-on-launch', 'Values': ['true']}
                ]
            )
            task_subnets = [s['SubnetId'] for s in public_subnets_response['Subnets']]
            
            if not task_subnets:
                logger.error(f"No public subnets found in VPC {vpc_id}")
                return {"success": False, "error": "No public subnets available"}
            
            logger.info(f"Using public subnets: {task_subnets}")
            
            # Run Fargate task with security group
            response = ecs.run_task(
                cluster=cluster,
                taskDefinition=task_definition,
                launchType='FARGATE',
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'subnets': task_subnets,
                        'securityGroups': [security_group],  # Security group with outbound access
                        'assignPublicIp': 'ENABLED'  # Need public IP for GitHub access
                    }
                },
                overrides={
                    'containerOverrides': [
                        {
                            'name': 'AgentContainer',
                            'environment': [
                                {
                                    'name': 'PROJECT_ID',
                                    'value': project_id
                                }
                            ]
                        }
                    ]
                }
            )
            
            task_arn = response['tasks'][0]['taskArn'] if response['tasks'] else None
            logger.info(f"Fargate task started: {task_arn}")
            
            return {
                "success": True,
                "task_arn": task_arn,
                "message": "Fargate agent started successfully"
            }
            
        except Exception as e:
            logger.error(f"Failed to trigger Fargate: {e}")
            return {"success": False, "error": str(e)}
    
    def run_autonomous_loop(self, site_url: str, repo_url: str, project_id: str, progress_callback=None) -> Dict[str, Any]:
        """
        Main AgentCore autonomous loop: Plan → Act → Verify
        This orchestrates all primitives to achieve the goal
        """
        logger.info(f"Starting autonomous loop for project {project_id}")
        results = {
            "project_id": project_id,
            "steps": [],
            "status": "in_progress"
        }
        
        def report_progress(step, progress, message):
            if progress_callback:
                progress_callback(step, progress, message)
        
        try:
            logger.info("Step 1: Scanning website for accessibility issues")
            report_progress("Scanning website", 20, "Running Lighthouse accessibility audit...")
            
            scan_result = self.invoke_tool("scan_site", {
                "site_url": site_url,
                "project_id": project_id
            })
            results["steps"].append({"step": "scan", "result": scan_result})
            
            if "error" in scan_result:
                results["status"] = "error"
                results["error"] = scan_result["error"]
                return results
            
            scan_data = json.loads(scan_result.get("body", "{}")) if "body" in scan_result else scan_result
            issues = scan_data.get("issues", [])
            score = scan_data.get("score", 0)
            
            report_progress("Scan complete", 35, f"Found {len(issues)} accessibility issues. Score: {score}/100")
            
            if not issues:
                results["status"] = "completed"
                results["message"] = "No accessibility issues found"
                return results
            
            logger.info(f"Step 2: Reasoning about {len(issues)} issues")
            report_progress("Analyzing issues", 45, f"AI analyzing {len(issues)} accessibility violations...")
            
            reasoning = self.reason({"issues": issues})
            results["steps"].append({"step": "reason", "result": reasoning})
            
            # NEW AGENTIC APPROACH: Skip patch generation in Lambda
            # AI will run entirely inside Fargate with full codebase access
            logger.info("Step 3: Launching agentic Fargate agent (AI will run inside container)")
            report_progress("Launching AI agent", 60, "Starting agentic Fargate agent with full codebase access...")
            
            # Store only issues and reasoning in DynamoDB for Fargate to access
            # Fargate agent will:
            # 1. Clone entire repo
            # 2. AI analyzes all files
            # 3. AI makes fixes iteratively
            # 4. AI builds and fixes build errors
            # 5. Repeats until build passes
            # 6. Pushes PR
            table = boto3.resource('dynamodb').Table(os.environ['DYNAMODB_TABLE'])
            table.update_item(
                Key={"project_id": project_id},
                UpdateExpression="SET agent_results = :results",
                ExpressionAttributeValues={
                    ":results": json.dumps({
                        "issues": issues,
                        "reasoning": reasoning[:500]
                    })
                }
            )
            
            # Trigger Fargate task
            fargate_result = self._trigger_fargate_agent(project_id)
            results["steps"].append({"step": "fargate_triggered", "result": fargate_result})
            
            if fargate_result.get("success"):
                report_progress("Agent started", 80, "Fargate agent is cloning repo and building...")
                # Fargate will handle:
                # - Clone repo
                # - Install dependencies  
                # - Apply patches
                # - Run build
                # - Run lint
                # - Push changes
                # - Create PR
                # - Update DynamoDB with final results
                results["status"] = "processing"
                results["message"] = "Fargate agent is building and verifying changes. Check status for updates."
                
                logger.info(f"Autonomous loop handed off to Fargate for project {project_id}")
            else:
                report_progress("Agent failed", 80, f"Could not start agent: {fargate_result.get('error', 'Unknown error')}")
                results["status"] = "error"
                results["error"] = fargate_result.get("error")
            
            # Note: Verification will be done by Fargate after PR creation
            # Fargate will update DynamoDB with pr_url, pr_number, branch_name, and improvement data
            return results
            
        except Exception as e:
            logger.error(f"Error in autonomous loop: {str(e)}")
            report_progress("Error", 0, f"Error occurred: {str(e)}")
            results["status"] = "error"
            results["error"] = str(e)
            return results

