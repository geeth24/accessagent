"""
Tool definitions for Bedrock AgentCore
Each tool represents a capability the agent can invoke
"""

TOOLS = [
    {
        "toolSpec": {
            "name": "scan_site",
            "description": "Run Lighthouse and axe-core accessibility audit on a website. Returns top accessibility violations with WCAG rule IDs, severity, and affected elements.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "site_url": {
                            "type": "string",
                            "description": "The full URL of the website to scan (must include http:// or https://)"
                        },
                        "project_id": {
                            "type": "string",
                            "description": "Unique identifier for this accessibility audit project"
                        }
                    },
                    "required": ["site_url", "project_id"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "generate_patch",
            "description": "Analyze accessibility issues and generate unified diff patches to fix them. Uses reasoning to determine the safest, most effective fixes.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "issues": {
                            "type": "array",
                            "description": "Array of accessibility issues from the scan, each containing selector, rule, severity, and context",
                            "items": {
                                "type": "object"
                            }
                        },
                        "repo_url": {
                            "type": "string",
                            "description": "GitHub repository URL (format: https://github.com/owner/repo)"
                        },
                        "project_id": {
                            "type": "string",
                            "description": "Project identifier to track this fix operation"
                        }
                    },
                    "required": ["issues", "repo_url", "project_id"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "apply_patch",
            "description": "Apply generated patches to the GitHub repository, create a new branch, commit changes, and open a pull request with a detailed description of accessibility improvements.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "patches": {
                            "type": "array",
                            "description": "Array of unified diff patches to apply to repository files",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file_path": {"type": "string"},
                                    "patch": {"type": "string"}
                                }
                            }
                        },
                        "repo_url": {
                            "type": "string",
                            "description": "GitHub repository URL"
                        },
                        "project_id": {
                            "type": "string",
                            "description": "Project identifier"
                        },
                        "summary": {
                            "type": "string",
                            "description": "Human-readable summary of the fixes for the PR description"
                        }
                    },
                    "required": ["patches", "repo_url", "project_id", "summary"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "verify_fix",
            "description": "Re-run accessibility audit on the PR preview deployment and compare results with the original scan. Returns improvement metrics and delta analysis.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "preview_url": {
                            "type": "string",
                            "description": "URL of the PR preview deployment to audit"
                        },
                        "project_id": {
                            "type": "string",
                            "description": "Project identifier to retrieve original scan results"
                        }
                    },
                    "required": ["preview_url", "project_id"]
                }
            }
        }
    }
]


def get_tool_by_name(tool_name: str):
    """Get tool definition by name"""
    for tool in TOOLS:
        if tool["toolSpec"]["name"] == tool_name:
            return tool
    return None

