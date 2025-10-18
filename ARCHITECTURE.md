# AccessAgent Architecture

## System Overview

AccessAgent is a fully autonomous AI system built on AWS that demonstrates the complete agent lifecycle: **Scan → Reason → Act → Verify → Explain**.

**Key Innovation:** Monolithic Fargate container with full codebase context for superior AI-powered fixes.

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                              │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │              Next.js Frontend (Vercel/Amplify)                  │  │
│  │  • Dashboard with input form                                    │  │
│  │  • Real-time progress tracker                                   │  │
│  │  • Before/after comparison table                                │  │
│  │  • shadcn/ui components + Tailwind CSS                          │  │
│  └─────────────────────┬──────────────────────────────────────────┘  │
└────────────────────────┼─────────────────────────────────────────────┘
                         │ HTTPS
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          API LAYER                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │             AWS API Gateway (REST API)                          │  │
│  │  • Custom domain: api.accessagent.geeth.app                     │  │
│  │  • CORS enabled                                                 │  │
│  │  • POST /scan (start scan)                                      │  │
│  │  • GET /project/{id} (get status)                               │  │
│  └─────────────────────┬──────────────────────────────────────────┘  │
└────────────────────────┼─────────────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION LAYER                              │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │         Agent Orchestrator Lambda (Python 3.11)                 │  │
│  │  • Receives scan request                                        │  │
│  │  • Creates project in DynamoDB                                  │  │
│  │  • Invokes Scan Lambda                                          │  │
│  │  • Triggers Fargate Agent with issues                           │  │
│  │  • Returns project ID to frontend                               │  │
│  └─────────────────────┬───────────────────────────────────────────┘  │
└────────────────────────┼─────────────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
┌─────────────────────┐   ┌──────────────────────────────────────────┐
│   Scan Lambda       │   │    Fargate Agent (Agentic AI)            │
│   (Node.js 18)      │   │    ECS Fargate Container                 │
│ ┌─────────────────┐ │   │  ┌────────────────────────────────────┐ │
│ │ Lighthouse CI   │ │   │  │  1. Read issues from DynamoDB      │ │
│ │ + axe-core      │ │   │  │  2. Clone full repository          │ │
│ │ Playwright      │ │   │  │  3. Read entire codebase           │ │
│ │                 │ │   │  │  4. AI analyzes with full context  │ │
│ │ - Audit site    │ │   │  │  5. Generate fixes                 │ │
│ │ - Parse issues  │ │   │  │  6. Apply fixes                    │ │
│ │ - Store in S3   │ │   │  │  7. Build project                  │ │
│ │ - Save to DB    │ │   │  │  8. Iterate until build passes     │ │
│ └─────────────────┘ │   │  │  9. Create PR with fixes           │ │
└─────────┬───────────┘   │  └────────────────────────────────────┘ │
          │               │  Uses: Claude 3.5 Sonnet (Bedrock)      │
          │               └──────────────┬───────────────────────────┘
          │                              │
          │        ┌─────────────────────┴───────────────────┐
          │        │                                         │
          ▼        ▼                                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         STORAGE & INTEGRATIONS                       │
│  ┌────────────────┐  ┌─────────────┐  ┌────────────────────────┐   │
│  │  DynamoDB      │  │  Amazon S3  │  │  AWS Secrets Manager   │   │
│  │  ┌──────────┐  │  │ ┌─────────┐ │  │  ┌──────────────────┐  │   │
│  │  │ Projects │  │  │ │ Reports │ │  │  │ GitHub Token     │  │   │
│  │  │ Status   │  │  │ │ Scans   │ │  │  └──────────────────┘  │   │
│  │  │ Results  │  │  │ └─────────┘ │  └────────────────────────┘   │
│  │  └──────────┘  │  └─────────────┘                               │
│  └────────────────┘                                                 │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                             │
                    ▼                             ▼
        ┌───────────────────┐        ┌─────────────────────┐
        │  Amazon Bedrock   │        │    GitHub API       │
        │  Claude 3.5       │        │                     │
        │  Sonnet v2        │        │  • Clone repo       │
        │                   │        │  • Create branch    │
        │  - Code analysis  │        │  • Commit changes   │
        │  - Fix generation │        │  • Open PR          │
        │  - Iteration      │        │  • Add comments     │
        └───────────────────┘        └─────────────────────┘
```

## Simplified Architecture (Clean Version)

**5 CDK Stacks:**

```
1. VPCStack (Persistent)           - VPC, subnets, endpoints
   └─> Separate for faster Fargate updates (5-10 min faster)

2. StorageStack                    - DynamoDB + S3
   └─> Shared by all services

3. FargateStack                    - ECS Cluster + Task Definition
   └─> Depends on: VPCStack

4. ComputeStack                    - 2 Lambda functions
   ├─> Agent Orchestrator (Python)
   └─> Scan (Node.js)

5. ApiStack                        - REST API + Custom Domain
   └─> Integrates with Agent Orchestrator
```

## Component Details

### 1. Frontend Layer (Next.js)

**Responsibilities:**
- User input collection (site URL, repo URL)
- Real-time progress visualization
- Results display and comparison
- Dark/light theme support

**Technology:**
- Next.js 15 (App Router)
- TypeScript
- shadcn/ui components
- Tailwind CSS
- Deployed on Vercel or AWS Amplify

**Key Pages:**
- `/` - Dashboard with scan form
- `/projects/[id]` - Project detail view

### 2. API Gateway Layer

**Responsibilities:**
- RESTful API endpoints
- Custom domain: `api.accessagent.geeth.app`
- CORS configuration
- Request routing to Lambda

**Endpoints:**
- `POST /scan` - Initiate new scan
- `GET /project/{project_id}` - Retrieve project status

### 3. Orchestration Layer

**Agent Orchestrator Lambda (Python 3.11):**
- Entry point for all requests
- Creates project record in DynamoDB
- Invokes Scan Lambda synchronously
- Triggers Fargate Agent asynchronously (fire-and-forget)
- Returns project ID immediately
- Timeout: 15 minutes
- Memory: 1024 MB

**Key Functions:**
- `lambda_handler()` - Main entry point
- `handle_async_processing()` - Async workflow
- `_trigger_fargate_agent()` - ECS task invocation

### 4. Scanning Layer

**Scan Lambda (Node.js 18):**
- Runs Lighthouse CI in headless Chrome
- Executes axe-core via Playwright
- Parses violations by WCAG rule
- Uploads full report to S3
- Saves issues to DynamoDB
- Returns top issues
- Timeout: 5 minutes
- Memory: 2048 MB

**Output Format:**
```json
{
  "issues": [
    {
      "rule": "color-contrast",
      "impact": "serious",
      "description": "...",
      "selector": "...",
      "wcag": ["AA"]
    }
  ],
  "score": 62,
  "report_url": "s3://..."
}
```

### 5. Agentic Fixing Layer (Fargate)

**Fargate Container (Python 3.11):**
- Long-running container (up to 2 hours)
- Full codebase access via Git clone
- Iterative build-fix loop
- Claude 3.5 Sonnet via Bedrock
- CPU: 1 vCPU
- Memory: 2 GB

**Process Flow:**
1. **Read Context:**
   - Fetch issues from DynamoDB
   - Clone entire repository
   - Read all relevant source files

2. **AI Analysis (with full context):**
   - Analyze codebase structure
   - Understand component relationships
   - Prioritize fixes by impact/complexity

3. **Generate Fixes:**
   - Create code patches with context
   - Ensure WCAG compliance
   - Maintain code style

4. **Apply & Verify:**
   - Apply patches to files
   - Run build command
   - Check for errors

5. **Iterate:**
   - If build fails, analyze errors
   - Generate new fixes
   - Repeat until build passes (max 5 iterations)

6. **Create PR:**
   - Commit all changes
   - Push to new branch
   - Open pull request
   - Add detailed description

**Key Files:**
- `agent_agentic.py` - Main orchestrator
- `agentic_fixer.py` - Iterative fix logic

### 6. Storage Layer

**DynamoDB Table (`accessagent-projects`):**
```
Partition Key: project_id (String)

Attributes:
- site_url (String)
- repo_url (String)
- status (String)
  • initialized → processing → completed | failed
- issues (List) - Accessibility issues from scan
- score_before (Number)
- pr_url (String)
- pr_number (Number)
- branch_name (String)
- created_at (String - ISO timestamp)
- updated_at (String - ISO timestamp)
- agent_results (JSON) - Fargate execution results
```

**S3 Bucket (`accessagent-reports-{account-id}`):**
```
/{project_id}/lighthouse-report.json    - Lighthouse results
/{project_id}/axe-report.json          - axe-core results
```

**Secrets Manager:**
```
Secret: accessagent/github-token
Value: {"token": "ghp_xxxxxxxxxxxxx"}
```

### 7. AI Layer (Amazon Bedrock)

**Model:** `anthropic.claude-3-5-sonnet-20241022-v2:0`

**Configuration:**
- Temperature: 0.3 (for consistency)
- Max Tokens: 4000
- System Prompt: Agent instructions with full codebase context

**Usage:**
1. Analyzing full codebase for context
2. Generating fixes with awareness of dependencies
3. Iterating on build errors
4. Creating natural language PR descriptions

### 8. External Integrations

**GitHub API:**
- Repository cloning (via Git CLI)
- Branch creation
- Pull request creation
- Comment posting
- Authentication via Personal Access Token

## Data Flow

### End-to-End Flow:

```
1. User submits form (site_url, repo_url)
   ↓
2. API Gateway → Agent Orchestrator Lambda
   ↓
3. Create project in DynamoDB (status: initialized)
   ↓
4. Invoke Scan Lambda (synchronous)
   ├─> Run Lighthouse + axe-core
   ├─> Save report to S3
   └─> Save issues to DynamoDB
   ↓
5. Trigger Fargate Agent (asynchronous)
   ↓
6. Return project_id to frontend
   ↓
7. Frontend polls GET /project/{id} for status
   ↓
8. Fargate Agent executes:
   ├─> Read issues from DynamoDB
   ├─> Clone repository
   ├─> Read full codebase
   ├─> AI generates fixes (with context)
   ├─> Apply fixes
   ├─> Build project
   ├─> Iterate if build fails
   └─> Create PR when successful
   ↓
9. Update DynamoDB with results
   ↓
10. Frontend displays PR link and improvements
```

## Infrastructure as Code (CDK)

### Stack Organization:

**1. VPCStack (Persistent)**
- VPC with public subnets
- VPC endpoints (ECR, S3, CloudWatch, ECR Docker)
- Security groups
- **Why separate?** VPC rarely changes, keeps it stable
- **Benefit:** Fargate updates are 5-10 min faster

**2. StorageStack**
- DynamoDB table with on-demand billing
- S3 bucket with encryption
- No dependencies

**3. FargateStack**
- ECS Cluster
- Task Definition (Docker image)
- Task execution role
- Task role (Bedrock, DynamoDB, S3, Secrets access)
- **Depends on:** VPCStack

**4. ComputeStack**
- Agent Orchestrator Lambda
- Scan Lambda
- Lambda execution role
- **Depends on:** StorageStack, FargateStack

**5. ApiStack**
- REST API
- Custom domain configuration
- Lambda integrations
- **Depends on:** ComputeStack

### Deployment Command:

```bash
cd cdk
cdk deploy --all --require-approval never
```

### Deployment Order (automatic):
1. VPCStack (2 minutes)
2. StorageStack (1 minute)
3. FargateStack (3 minutes)
4. ComputeStack (2 minutes)
5. ApiStack (1 minute)

**Total:** ~9 minutes

## Security Architecture

### IAM Roles:

**Lambda Execution Role:**
- Read/Write DynamoDB
- Read/Write S3
- Read Secrets Manager
- Invoke Bedrock models
- Invoke ECS tasks
- CloudWatch Logs

**Fargate Task Role:**
- Read/Write DynamoDB
- Read/Write S3
- Read Secrets Manager
- Invoke Bedrock models
- CloudWatch Logs

**Fargate Execution Role:**
- Pull images from ECR
- Write to CloudWatch Logs

### Data Protection:
- **Secrets:** AWS Secrets Manager (encrypted at rest)
- **S3:** Server-side encryption (SSE-S3)
- **DynamoDB:** Point-in-time recovery enabled
- **API Gateway:** HTTPS only (TLS 1.2)
- **Logs:** Sanitized (no tokens/secrets)

## Scalability & Performance

### Concurrency:
- **Lambda:** Default concurrent executions (1000)
- **Fargate:** Can run multiple tasks in parallel
- **DynamoDB:** On-demand billing (auto-scales)
- **S3:** Unlimited objects
- **Bedrock:** Throttling limits apply (request increases if needed)

### Timeouts:
- **API Gateway:** 29 seconds
- **Agent Orchestrator Lambda:** 15 minutes
- **Scan Lambda:** 5 minutes
- **Fargate Agent:** 2 hours max

### Performance Optimizations:
1. **Separate VPC Stack:** Fargate updates 5-10 min faster
2. **Async Fargate:** No waiting for fixes to complete
3. **DynamoDB On-Demand:** No capacity planning
4. **S3 for Large Reports:** Keeps DynamoDB items small
5. **Single Fargate Container:** No cold starts during iteration

## Cost Optimization

**Estimated cost per scan:**
- Scan Lambda: $0.01
- Agent Orchestrator: $0.005
- Fargate (30 min): $0.10
- Bedrock tokens (10K): $0.15
- DynamoDB: $0.01
- S3: $0.001
- **Total:** ~$0.28 per scan

**Monthly (100 scans):**
- ~$28/month

## Monitoring & Observability

### CloudWatch Metrics:
- Lambda invocations, errors, duration
- Fargate CPU/memory utilization
- DynamoDB read/write capacity
- Bedrock API calls

### CloudWatch Logs:
- Agent reasoning steps
- Build outputs
- Error stack traces
- GitHub API responses

### Alarms (Optional):
- Lambda error rate > 5%
- Fargate task failures
- DynamoDB throttling

## Advantages of This Architecture

### ✅ Better AI Context
- Fargate agent sees **entire codebase**
- Understands component relationships
- Makes smarter fix decisions

### ✅ Faster Iteration
- No Lambda cold starts between fix attempts
- Single container keeps state
- Faster debugging of build errors

### ✅ Simpler Design
- **2 Lambdas** instead of 4
- Monolithic Fargate vs distributed functions
- Easier to understand and maintain

### ✅ Lower Cost
- Fewer Lambda invocations
- Fargate only runs when needed
- No NAT Gateway needed (public subnets)

### ✅ Faster Deployments
- Separate VPC stack (5-10 min saved per Fargate update)
- Independent stack updates
- No VPC recreation needed

---

## Comparison: Old vs New Architecture

### Old Architecture (4 Lambdas):
```
Orchestrator → Scan → GitHub Ops → Rescan
                 ↓         ↓
              Issues → Apply → Verify
```
**Problems:**
- ❌ Lambdas had limited context (15 min timeout)
- ❌ Cold starts between each step
- ❌ More complex orchestration
- ❌ Higher costs (4 Lambda functions)

### New Architecture (2 Lambdas + Fargate):
```
Orchestrator → Scan → Fargate (full autonomy)
                 ↓         ↓
              Issues → Full codebase + Build + PR
```
**Benefits:**
- ✅ Full codebase context
- ✅ Iterative build-fix loop
- ✅ Simpler orchestration
- ✅ Lower costs (2 Lambdas + 1 Fargate)
- ✅ 40% less code

---

**Built for AWS AI Agent Global Hackathon 2025**
