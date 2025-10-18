"""
MCP-powered codebase explorer for iterative file reading
Provides tools for the AI agent to search and read files on-demand
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
import subprocess

logger = logging.getLogger(__name__)

class MCPCodebaseExplorer:
    """
    Provides MCP-like tools for AI agent to explore codebase iteratively
    Mimics how Cursor/Claude work - search, read, analyze, repeat
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self.files_cache = {}
        
    def list_files(self, pattern: str = "*", max_results: int = 100) -> List[str]:
        """
        Tool: list_files
        Search for files matching a glob pattern
        """
        try:
            files = list(self.repo_path.rglob(pattern))
            # Filter out common ignores
            files = [f for f in files if all(ignore not in str(f) for ignore in [
                'node_modules', '.git', 'dist', 'build', '.next', '__pycache__'
            ])]
            results = [str(f.relative_to(self.repo_path)) for f in files[:max_results]]
            logger.info(f"list_files({pattern}): found {len(results)} files")
            return results
        except Exception as e:
            logger.error(f"list_files error: {e}")
            return []
    
    def read_file(self, file_path: str) -> Dict[str, Any]:
        """
        Tool: read_file
        Read complete contents of a file
        """
        try:
            full_path = self.repo_path / file_path
            
            if not full_path.exists():
                return {"error": f"File not found: {file_path}"}
            
            if full_path.stat().st_size > 100000:  # 100KB limit
                return {"error": f"File too large: {file_path}"}
            
            content = full_path.read_text(encoding='utf-8')
            self.files_cache[file_path] = content
            
            logger.info(f"read_file({file_path}): {len(content)} chars")
            
            return {
                "file_path": file_path,
                "content": content,
                "size": len(content)
            }
        except Exception as e:
            logger.error(f"read_file error: {e}")
            return {"error": str(e)}
    
    def search_content(self, pattern: str, file_types: List[str] = None) -> List[Dict[str, str]]:
        """
        Tool: search_content
        Search for content in files using ripgrep-like search
        """
        try:
            # Use grep since ripgrep might not be available
            cmd = ["grep", "-r", "-n", "-i", pattern, "."]
            if file_types:
                for ft in file_types:
                    cmd.extend(["--include", f"*.{ft}"])
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            matches = []
            for line in result.stdout.split('\n')[:50]:  # Limit to 50 matches
                if ':' in line:
                    parts = line.split(':', 2)
                    if len(parts) == 3:
                        matches.append({
                            "file": parts[0],
                            "line": parts[1],
                            "content": parts[2].strip()
                        })
            
            logger.info(f"search_content({pattern}): found {len(matches)} matches")
            return matches
            
        except Exception as e:
            logger.error(f"search_content error: {e}")
            return []
    
    def get_file_structure(self) -> str:
        """
        Tool: get_file_structure
        Get tree-like structure of the repository
        """
        try:
            # Find important directories
            key_dirs = [
                "src", "app", "pages", "components", 
                "lib", "utils", "styles", "public"
            ]
            
            structure = []
            for dir_name in key_dirs:
                dir_path = self.repo_path / dir_name
                if dir_path.exists():
                    # List files in this directory
                    files = [f.relative_to(self.repo_path) for f in dir_path.rglob("*") if f.is_file()]
                    structure.append(f"\n{dir_name}/")
                    for f in files[:20]:  # Limit per directory
                        structure.append(f"  {f}")
            
            result = "\n".join(structure)
            logger.info(f"get_file_structure: {len(structure)} entries")
            return result
            
        except Exception as e:
            logger.error(f"get_file_structure error: {e}")
            return ""
    
    def get_package_info(self) -> Dict[str, Any]:
        """
        Tool: get_package_info
        Read package.json to understand framework and dependencies
        """
        try:
            package_file = self.repo_path / "package.json"
            if not package_file.exists():
                return {"error": "No package.json found"}
            
            content = package_file.read_text()
            package_data = json.loads(content)
            
            # Extract key info
            info = {
                "name": package_data.get("name"),
                "framework": None,
                "dependencies": list(package_data.get("dependencies", {}).keys()),
                "devDependencies": list(package_data.get("devDependencies", {}).keys()),
                "scripts": package_data.get("scripts", {})
            }
            
            # Detect framework
            if "next" in info["dependencies"]:
                info["framework"] = "Next.js"
            elif "react" in info["dependencies"]:
                info["framework"] = "React"
            elif "vue" in info["dependencies"]:
                info["framework"] = "Vue"
            
            logger.info(f"get_package_info: {info['framework']}, {len(info['dependencies'])} deps")
            return info
            
        except Exception as e:
            logger.error(f"get_package_info error: {e}")
            return {"error": str(e)}
    
    def generate_tool_descriptions(self) -> str:
        """
        Generate tool descriptions for AI agent prompt
        """
        return """
**Available MCP Tools for Codebase Exploration:**

1. **list_files(pattern)** - Search for files matching glob pattern
   Example: list_files("**/*.tsx") - finds all TypeScript React files
   
2. **read_file(file_path)** - Read complete contents of a file
   Example: read_file("src/components/Button.tsx")
   
3. **search_content(pattern, file_types)** - Search for text in files
   Example: search_content("className", ["tsx", "jsx"])
   
4. **get_file_structure()** - Get tree view of repository structure
   
5. **get_package_info()** - Get framework and dependency information

**How to use:**
1. Start with get_package_info() and get_file_structure() to understand the project
2. Use list_files() to find relevant files
3. Use read_file() to read specific files you need
4. Use search_content() to find specific patterns

**Iterative approach:**
- Don't try to read all files at once
- Read files as you need them based on the issues
- Use search to find where specific elements are defined
"""
