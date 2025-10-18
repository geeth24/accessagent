"""
Agentic Build-Fix Loop
AI agent runs inside Fargate with full codebase access
Makes fixes iteratively until build passes
"""
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Any
import boto3

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
        self.model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        
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
    
    def call_claude(self, system_prompt: str, user_message: str) -> str:
        """
        Call Claude Sonnet to analyze and generate fixes
        """
        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "system": system_prompt,
                    "messages": [{
                        "role": "user",
                        "content": user_message
                    }],
                    "temperature": 0.1
                })
            )
            
            result = json.loads(response['body'].read())
            return result['content'][0]['text']
            
        except Exception as e:
            logger.error(f"Bedrock API error: {e}")
            raise
    
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
        
        system_prompt = """You are an expert accessibility engineer.
You have full access to a codebase and must fix accessibility violations.

CRITICAL RULES:
1. Read the ENTIRE codebase context provided
2. Make MINIMAL changes - only fix accessibility issues
3. DO NOT refactor, reformat, or add comments
4. DO NOT change build configuration or dependencies
5. Output ONLY valid JSON with your changes
6. Use SHORT substrings (15-40 chars) that uniquely identify lines

Output format:
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
                user_message = f"""# CODEBASE
{codebase_context}

# ACCESSIBILITY ISSUES TO FIX
{json.dumps(self.issues[:10], indent=2)}

Analyze the code and fix these accessibility issues with minimal changes.
Output JSON with your fixes."""
            else:
                # Subsequent iterations: fix build errors
                user_message = f"""# PREVIOUS BUILD FAILED
Error output:
{build_errors['error'][:2000]}

{codebase_context}

The build failed. Read the error carefully and fix ONLY what's causing the build to fail.
Output JSON with your fixes."""
            
            # Get AI response
            logger.info("Calling Claude for fixes...")
            ai_response = self.call_claude(system_prompt, user_message)
            
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

