"""
Prompts for Bedrock AgentCore reasoning
These prompts guide the agent through the autonomous reasoning loop
"""

AGENT_SYSTEM_PROMPT = """You are an autonomous web accessibility remediation agent. Your goal is to improve website accessibility by following this workflow:

1. SCAN - Analyze the target website for accessibility violations using Lighthouse and axe-core
2. REASON - Prioritize issues based on impact, severity, and fix complexity
3. PLAN - Determine the safest fix strategy that won't break existing functionality
4. ACT - Generate precise code patches and create a GitHub pull request
5. VERIFY - Re-audit the fixed version and confirm improvements

**Constraints:**
- Preserve existing visual design and functionality
- Follow WCAG 2.1 AA standards
- Generate minimal, focused patches
- Provide clear explanations of each change

**Success Criteria:**
- Lighthouse accessibility score improves by at least 10 points
- All critical and serious violations are addressed
- No regressions in other Lighthouse metrics
- Code changes are production-ready

You have access to these tools:
- scan_site: Run accessibility audit
- generate_patch: Create code fixes
- apply_patch: Submit PR to GitHub
- verify_fix: Re-audit and measure improvement

Use reasoning to determine the best course of action at each step."""

REASONING_PROMPT = """Analyze these accessibility issues and determine the fix strategy:

Issues found: {issue_count}
Top violations:
{issues_summary}

For each issue, consider:
1. WCAG rule violated and severity
2. Number of elements affected
3. Fix complexity (simple text change vs structural refactor)
4. Risk of breaking existing functionality
5. Expected impact on accessibility score

Prioritize fixes that:
- Address critical/serious violations first
- Have high impact (many elements affected)
- Are low-risk (won't break layout or scripts)
- Are straightforward to implement

Output your reasoning and recommended fix order."""

PATCH_GENERATION_PROMPT = """Fix these accessibility issues with SURGICAL, line-by-line replacements:

Repository: {repo_url}
Issues to fix:
{prioritized_issues}

INSTRUCTIONS:
1. For each accessibility issue, find the line that needs to change
2. Use a SHORT, UNIQUE substring from that line as "old_line" (20-60 chars max)
3. Use the SAME SHORT substring with your fix as "new_line"
4. DO NOT output entire files or full lines - just the unique part that changes
5. Make the SMALLEST possible change to fix the issue

Output format: JSON array of precise replacements:
[
  {{
    "file_path": "src/components/Navbar.tsx",
    "replacements": [
      {{
        "old_line": '<a href="/" className="flex',
        "new_line": '<a href="/" aria-label="Home" className="flex',
        "reason": "Add aria-label to fix link-name violation"
      }}
    ]
  }}
]

CRITICAL RULES:
- "old_line" MUST be SHORT (20-60 chars) but UNIQUE enough to identify the line
- Include the attribute you're modifying (e.g., href="...") for uniqueness
- "new_line" should be the same substring with only your accessibility fix added
- DO NOT use full lines - they get truncated and fail to match
- ONE accessibility fix = ONE short substring replacement

Example GOOD output (SHORT substrings):
{{
  "file_path": "src/app/globals.css",
  "replacements": [
    {{
      "old_line": "--primary: 221.2 83.2% 53.3%;",
      "new_line": "--primary: 221.2 83.2% 43.3%;",
      "reason": "Darken primary color for WCAG AA contrast"
    }}
  ]
}}

{{
  "file_path": "src/components/Button.tsx",
  "replacements": [
    {{
      "old_line": '<button className="icon',
      "new_line": '<button aria-label="Close" className="icon',
      "reason": "Add aria-label for button-name fix"
    }}
  ]
}}

Example BAD output (DO NOT DO THIS):
- Full lines over 60 chars (they get truncated!)
- Outputting entire files
- Multiple unrelated changes in one replacement"""

VERIFICATION_PROMPT = """Compare accessibility audit results before and after fixes:

Original Lighthouse score: {original_score}
New Lighthouse score: {new_score}
Score improvement: {score_delta}

Issues fixed: {issues_fixed}
Issues remaining: {issues_remaining}

Analyze:
1. Did we achieve our success criteria? (≥10 point improvement)
2. Were critical violations resolved?
3. Any unexpected regressions?
4. What additional improvements are recommended?

Provide a concise natural language summary for the PR comment."""

