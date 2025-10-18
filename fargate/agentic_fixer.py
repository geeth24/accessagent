"""
Agentic Build-Fix Loop
AI agent runs inside Fargate with full codebase access
Makes fixes iteratively until build passes
Uses MCP-like tools for iterative exploration
"""
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Any
import boto3
from mcp_explorer import MCPCodebaseExplorer

logger = logging.getLogger(__name__)

class AgenticFixer:
    """
    AI agent that:
    1. Reads entire codebase
    2. Analyzes accessibility issues
    3. Makes fixes
    4. Builds project
    5. If build fails: reads errors, fixes them, tries again
    6. Repeats until build passes
    """

    def __init__(self, repo_path: str, issues: List[Dict], bedrock_client=None):
        self.repo_path = Path(repo_path)
        self.issues = issues
        self.bedrock_client = bedrock_client or boto3.client('bedrock-runtime', region_name='us-east-1')
        self.max_iterations = 5
        self.model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"  # Inference profile for Claude 3.5 Sonnet v2
        self.mcp_explorer = MCPCodebaseExplorer(str(repo_path))

    def get_codebase_context(self, max_files=30, max_size=5000) -> str:
        """
        Read key files from repo to give AI full context
        Searches recursively for all component files
        """
        logger.info(f"Reading codebase from {self.repo_path}")

        # Comprehensive patterns for all common React/Next.js structures
        priority_patterns = [
            # Next.js TypeScript
            "src/components/**/*.tsx",
            "src/components/**/*.ts", 
            "src/app/**/*.tsx",
            "src/app/**/*.ts",
            # Next.js JavaScript
            "src/components/**/*.jsx",
            "src/components/**/*.js",
            "src/app/**/*.jsx",
            "src/app/**/*.js",
            # Standard React
            "components/**/*.jsx",
            "components/**/*.js",
            "pages/**/*.jsx",
            "pages/**/*.js",
            # Root level App
            "src/*.jsx",
            "src/*.js",
            "src/*.tsx",
            "src/*.ts",
            # Styles
            "src/**/*.css",
            "**/*.css",
        ]

        files_content = []
        files_read = 0

        for pattern in priority_patterns:
            if files_read >= max_files:
                break

            for file_path in self.repo_path.glob(pattern):
                if files_read >= max_files:
                    break

                try:
                    if file_path.stat().st_size > max_size:
                        continue

                    content = file_path.read_text(encoding='utf-8')
                    rel_path = file_path.relative_to(self.repo_path)
                    files_content.append(f"=== {rel_path} ===\n{content}\n")
                    files_read += 1
                    logger.info(f"  ✓ Read: {rel_path}")

                except Exception as e:
                    logger.warning(f"Could not read {file_path}: {e}")

        logger.info(f"Read {files_read} files total from codebase")

        # Add file list at the start so AI knows what files exist
        file_list = "\n".join([f"- {f.relative_to(self.repo_path)}" for f in self.repo_path.rglob("*.jsx") if f.is_file()][:50])
        file_list += "\n" + "\n".join([f"- {f.relative_to(self.repo_path)}" for f in self.repo_path.rglob("*.js") if f.is_file()][:50])
        file_list += "\n" + "\n".join([f"- {f.relative_to(self.repo_path)}" for f in self.repo_path.rglob("*.tsx") if f.is_file()][:50])

        return f"# AVAILABLE FILES IN REPO:\n{file_list}\n\n# FILE CONTENTS:\n" + "\n".join(files_content)

    def get_mcp_tools(self) -> List[Dict]:
        """Define MCP tools that Claude can use"""
        return [
            {
                "name": "list_files",
                "description": "Search for files in the repository matching a glob pattern. Use to discover relevant files.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Glob pattern (e.g., '**/*.tsx' for all TypeScript React files)"
                        }
                    },
                    "required": ["pattern"]
                }
            },
            {
                "name": "read_file",
                "description": "Read the complete contents of a file. Use this to analyze code before making fixes.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file relative to repo root"
                        }
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "search_content",
                "description": "Search for text patterns across files. Use to find where specific elements or classes are used.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Text pattern to search for"
                        },
                        "file_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File extensions to search in (e.g., ['tsx', 'jsx'])"
                        }
                    },
                    "required": ["pattern"]
                }
            },
            {
                "name": "get_package_info",
                "description": "Get framework and dependency information from package.json",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]

    def execute_tool(self, tool_name: str, tool_input: Dict) -> Any:
        """Execute an MCP tool and return the result"""
        try:
            if tool_name == "list_files":
                return self.mcp_explorer.list_files(tool_input.get("pattern", "*"))
            elif tool_name == "read_file":
                return self.mcp_explorer.read_file(tool_input["file_path"])
            elif tool_name == "search_content":
                return self.mcp_explorer.search_content(
                    tool_input["pattern"],
                    tool_input.get("file_types")
                )
            elif tool_name == "get_package_info":
                return self.mcp_explorer.get_package_info()
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}

    def call_claude_with_tools(self, system_prompt: str, user_message: str, max_tool_rounds: int = 3) -> str:
        """
        Call Claude Sonnet with MCP tools support
        Allows Claude to iteratively explore the codebase
        """
        messages = [{"role": "user", "content": user_message}]

        for round_num in range(max_tool_rounds):
            try:
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 8192,
                    "system": system_prompt,
                    "messages": messages,
                    "temperature": 0.1,
                    "tools": self.get_mcp_tools()
                }

                # Retry with exponential backoff for throttling
                max_retries = 3
                base_delay = 2

                for retry in range(max_retries):
                    try:
                        response = self.bedrock_client.invoke_model(
                            modelId=self.model_id,
                            contentType="application/json",
                            accept="application/json",
                            body=json.dumps(request_body),
                        )
                        break
                    except Exception as e:
                        if "ThrottlingException" in str(e) and retry < max_retries - 1:
                            wait_time = base_delay * (2**retry)
                            logger.warning(
                                f"Throttled, waiting {wait_time}s before retry {retry + 1}/{max_retries}"
                            )
                            time.sleep(wait_time)
                        else:
                            raise

                result = json.loads(response['body'].read())

                # Check stop reason
                stop_reason = result.get('stop_reason')

                if stop_reason == 'tool_use':
                    # Claude wants to use tools
                    logger.info(f"Tool use round {round_num + 1}")

                    # Add assistant response to messages
                    messages.append({
                        "role": "assistant",
                        "content": result['content']
                    })

                    # Execute tools and add results
                    tool_results = []
                    for content_block in result['content']:
                        if content_block.get('type') == 'tool_use':
                            tool_name = content_block['name']
                            tool_input = content_block['input']
                            tool_use_id = content_block['id']

                            logger.info(f"Executing tool: {tool_name}({json.dumps(tool_input)[:100]}...)")
                            tool_result = self.execute_tool(tool_name, tool_input)

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": json.dumps(tool_result)
                            })

                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                    # Continue loop to get next response
                    continue

                else:
                    # Claude is done, return text response
                    text_content = ""
                    for content_block in result['content']:
                        if content_block.get('type') == 'text':
                            text_content += content_block['text']

                    return text_content

            except Exception as e:
                logger.error(f"Bedrock API error: {e}")
                raise

        # Max rounds reached, return what we have
        return "Max tool rounds reached"

    def apply_ai_fixes(self, ai_response: str) -> int:
        """
        Parse AI response and apply file changes
        Returns number of files modified
        """
        # AI should return JSON with file edits
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in ai_response:
                ai_response = ai_response.split("```json")[1].split("```")[0]
            elif "```" in ai_response:
                ai_response = ai_response.split("```")[1].split("```")[0]

            edits = json.loads(ai_response.strip())
            modified_count = 0

            for edit in edits:
                file_path = self.repo_path / edit['file_path']

                if not file_path.exists():
                    logger.warning(f"File not found: {file_path}")
                    continue

                # Read current content
                content = file_path.read_text(encoding='utf-8')

                # Apply each replacement
                for replacement in edit.get('replacements', []):
                    old = replacement['old_line']
                    new = replacement['new_line']

                    if old in content:
                        content = content.replace(old, new, 1)
                        logger.info(f"✓ Applied fix to {edit['file_path']}: {replacement.get('reason', '')}")
                    else:
                        logger.warning(f"✗ Could not find: {old[:50]}... in {edit['file_path']}")

                # Write back
                file_path.write_text(content, encoding='utf-8')
                modified_count += 1

            return modified_count

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"AI response: {ai_response[:500]}")
            return 0

    def build_project(self) -> Dict[str, Any]:
        """
        Run pnpm install && pnpm build
        Returns: {success: bool, output: str, error: str}
        """
        logger.info("Building project...")

        try:
            # Install dependencies
            install_result = subprocess.run(
                ["pnpm", "install"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=300
            )

            if install_result.returncode != 0:
                return {
                    "success": False,
                    "stage": "install",
                    "output": install_result.stdout,
                    "error": install_result.stderr
                }

            # Build
            build_result = subprocess.run(
                ["pnpm", "build"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=600
            )

            return {
                "success": build_result.returncode == 0,
                "stage": "build",
                "output": build_result.stdout,
                "error": build_result.stderr
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stage": "timeout",
                "error": "Build timed out after 10 minutes"
            }
        except Exception as e:
            return {
                "success": False,
                "stage": "exception",
                "error": str(e)
            }

    def run_fix_loop(self) -> Dict[str, Any]:
        """
        Main agentic loop:
        1. Get full codebase context
        2. Ask AI to fix accessibility issues
        3. Apply fixes
        4. Build
        5. If build fails: give AI the error, ask it to fix
        6. Repeat until build passes or max iterations
        """
        logger.info(f"Starting agentic fix loop for {len(self.issues)} issues")

        # Get full codebase
        codebase_context = self.get_codebase_context()

        system_prompt = """You are an expert accessibility engineer with MCP tool access to explore codebases.

**Your approach (like Cursor/Claude):**
1. Use get_package_info() to understand the framework
2. Use list_files() to discover relevant files
3. Use read_file() to analyze specific files mentioned in issues
4. Use search_content() to find where specific elements are used
5. Make MINIMAL fixes to only what's needed

**Available tools:**
- list_files(pattern) - Find files matching glob pattern
- read_file(file_path) - Read complete file contents
- search_content(pattern, file_types) - Search for text in files
- get_package_info() - Get framework and dependencies

**CRITICAL RULES:**
1. Start by exploring the codebase with tools
2. Read actual files before making changes
3. Make MINIMAL changes - only fix accessibility issues
4. DO NOT refactor, reformat, or add comments
5. DO NOT change build configuration or dependencies
6. Output ONLY valid JSON with your changes
7. Use SHORT substrings (15-40 chars) that uniquely identify lines

**Output format (after exploration):**
[
  {
    "file_path": "src/components/Button.tsx",
    "replacements": [
      {
        "old_line": "<button className=\\"icon",
        "new_line": "<button aria-label=\\"Close\\" className=\\"icon",
        "reason": "Add aria-label for screen readers"
      }
    ]
  }
]"""

        iteration = 0
        build_errors = None

        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Iteration {iteration}/{self.max_iterations}")

            # Build prompt
            if iteration == 1:
                # First iteration: fix accessibility issues
                user_message = f"""# ACCESSIBILITY ISSUES TO FIX
{json.dumps(self.issues[:20], indent=2)}

**Your task:**
1. First, explore the codebase using tools (get_package_info, list_files, read_file)
2. Identify which files need changes to fix these issues
3. Read those files with read_file()
4. Output JSON with your fixes

Start by calling get_package_info() to understand the project structure."""
            else:
                # Subsequent iterations: fix build errors
                user_message = f"""# PREVIOUS BUILD FAILED
Error output:
{build_errors['error'][:2000]}

The build failed. Use tools to explore the codebase and fix ONLY what's causing the build to fail.
Start by reading the files mentioned in the error."""

            # Get AI response with tool use
            logger.info("Calling Claude with MCP tools...")
            ai_response = self.call_claude_with_tools(system_prompt, user_message, max_tool_rounds=5)

            # Apply fixes
            modified_count = self.apply_ai_fixes(ai_response)
            logger.info(f"Modified {modified_count} files")

            if modified_count == 0:
                logger.warning("AI made no changes")
                break

            # Build
            build_result = self.build_project()

            if build_result['success']:
                logger.info(f"✓ Build passed on iteration {iteration}!")
                return {
                    "success": True,
                    "iterations": iteration,
                    "files_modified": modified_count
                }
            else:
                logger.warning(f"✗ Build failed on iteration {iteration}")
                build_errors = build_result
                # Loop continues...

        # Max iterations reached
        return {
            "success": False,
            "iterations": iteration,
            "error": "Max iterations reached, build still failing",
            "last_build_error": build_errors
        }
