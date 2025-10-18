# AccessAgent: Autonomous Web Accessibility Remediation

<div align="center">

**An AI-powered agent that automatically scans websites for accessibility issues, generates fixes, and creates pull requests with verified improvements.**

Built with AWS Bedrock AgentCore | Claude 3.5 Sonnet | AWS Lambda | Next.js

[![AWS](https://img.shields.io/badge/AWS-Bedrock-orange)](https://aws.amazon.com/bedrock/)
[![AgentCore](https://img.shields.io/badge/AgentCore-Primitives-blue)](https://docs.aws.amazon.com/bedrock/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

---

## 🎯 Problem Statement

Over **1 billion people** worldwide live with disabilities, yet **98% of websites** fail to meet basic accessibility standards (WCAG 2.1 AA). This creates barriers that prevent millions from accessing essential services, information, and opportunities online.

Manual accessibility remediation is:
- ⏰ Time-consuming (weeks to months per site)
- 💰 Expensive (requires specialized expertise)
- 🔄 Difficult to maintain (new issues arise with each update)
- 📉 Often deprioritized in fast-paced development

## 💡 Solution

**AccessAgent** is an autonomous AI agent that follows AWS's AI Agent design principles:

```
Scan → Reason → Act → Verify → Explain
```

The agent:
1. **Scans** websites using Lighthouse and axe-core
2. **Reasons** about fix priorities using Bedrock AgentCore
3. **Acts** by generating code patches
4. **Verifies** improvements through re-auditing
5. **Explains** changes in natural language

### Key Innovation: Monolithic Fargate Agent

Unlike traditional multi-Lambda approaches, AccessAgent uses a **monolithic Fargate container** that:
- Has **full codebase context** (clones entire repository)
- **Iteratively builds and fixes** until the project compiles
- **Autonomously decides** when fixes are complete
- **Creates PR** with verified improvements

Benefits:
- ✅ **Better context** - AI sees full codebase, not just snippets
- ✅ **Faster iteration** - No cold starts between fix attempts
- ✅ **Lower cost** - Single container vs multiple Lambda invocations
- ✅ **Simpler architecture** - 2 Lambdas instead of 4

---

## 🏗️ Architecture

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │ HTTPS
       v
┌─────────────────────────────────────┐
│     Next.js Frontend                │
│  - Dashboard                        │
│  - Real-time Progress               │
│  - Results Visualization            │
└──────────────┬──────────────────────┘
               │ REST API
               v
┌──────────────────────────────────────┐
│  API Gateway (Custom Domain)         │
│  https://api.accessagent.geeth.app   │
└──────────────┬───────────────────────┘
               │
               v
┌──────────────────────────────────────┐
│   Agent Orchestrator Lambda          │
│   (Python 3.11 + Bedrock)            │
│   - Receives scan request            │
│   - Invokes scan Lambda              │
│   - Triggers Fargate agent           │
│   - Stores results in DynamoDB       │
└─────┬────────────────────────────────┘
      │
      v
┌─────────────┐
│  Scan       │  ← Lighthouse + axe-core (Node.js 18)
│  Lambda     │     Gets accessibility issues
└─────┬───────┘     Stores report in S3
      │
      │ Issues saved to DynamoDB
      v
┌──────────────────────────────────────┐
│  Fargate Container (Agentic AI)      │
│  (Claude 3.5 Sonnet via Bedrock)     │
│                                      │
│  1. Reads issues from DynamoDB       │
│  2. Clones full repository           │
│  3. AI analyzes full codebase        │
│  4. Generates & applies fixes        │
│  5. Builds project iteratively       │
│  6. Creates PR with fixes            │
└──────────────┬───────────────────────┘
               │
               v
┌──────────────────────────────────────┐
│  Storage & Integrations              │
│  - DynamoDB (project state)          │
│  - S3 (scan reports)                 │
│  - Secrets Manager (GitHub token)    │
│  - GitHub API (PR creation)          │
└──────────────────────────────────────┘

Infrastructure:
- VPC Stack (persistent, separate)
- Storage Stack (DynamoDB + S3)
- Fargate Stack (ECS cluster)
- Compute Stack (2 Lambdas)
- API Stack (REST API + custom domain)
```

---

## 🚀 Getting Started

### Prerequisites

- **AWS Account** with Bedrock access enabled
- **AWS CLI** configured with appropriate credentials
- **Node.js 18+** and **pnpm**
- **Python 3.11+**
- **GitHub Personal Access Token** (with `repo` scope)

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/accessagent-agent.git
cd accessagent-agent
```

#### 2. Set Up Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r cdk/requirements.txt
```

#### 3. Configure AWS

```bash
# Set your default region (us-east-1 recommended for Bedrock)
export AWS_DEFAULT_REGION=us-east-1

# Bootstrap CDK (first time only)
cd cdk
cdk bootstrap
```

#### 4. Store GitHub Token

```bash
# Create a secret in AWS Secrets Manager
aws secretsmanager create-secret \
  --name accessagent/github-token \
  --secret-string '{"token":"your_github_pat_here"}'
```

#### 5. Deploy Backend Infrastructure

```bash
cd cdk
cdk deploy --all --require-approval never
```

**Note:** This will create:
- **VPC Stack:** Persistent VPC with endpoints (separate for faster Fargate updates)
- **Storage Stack:** DynamoDB table + S3 bucket
- **Fargate Stack:** ECS Fargate cluster + task definition (agentic AI agent)
- **Compute Stack:** 2 Lambda functions (orchestrator, scan)
- **API Stack:** API Gateway with custom domain (`api.accessagent.geeth.app`)
- IAM roles with Bedrock permissions

#### 6. Set Up Frontend

```bash
cd ../frontend
pnpm install

# Create environment file
echo "NEXT_PUBLIC_API_URL=YOUR_API_GATEWAY_URL" > .env.local

# Run locally
pnpm dev
```

#### 7. Deploy Frontend to AWS Amplify

```bash
# Connect your GitHub repo to Amplify
# Build settings:
# - Build command: pnpm run build
# - Publish directory: .next
# - Node version: 18
```

---

## 📖 Usage

### Basic Flow

1. **Navigate to the dashboard** at `http://localhost:3000`
2. **Enter your website URL** (e.g., `https://example.com`)
3. **Enter your GitHub repository URL** (e.g., `https://github.com/user/repo`)
4. **Click "Run AccessAgent"**
5. **Watch the autonomous loop** execute in real-time
6. **Review the pull request** created by the agent
7. **Verify improvements** in the before/after comparison

### Example Output

```
✅ Scan completed: Found 27 accessibility issues
🧠 Agent reasoning: Prioritizing 15 high-impact fixes
🔧 Generated patches for 3 files
📝 Created PR: https://github.com/user/repo/pull/42
✅ Verification: Score improved from 62 → 93 (+31 points)
```

---

## 🧪 Testing

### Manual Testing

1. Use a test website with known accessibility issues
2. Use a GitHub repo you control
3. Run the full agent loop
4. Verify:
   - ✅ Scan completes successfully
   - ✅ Agent generates reasonable patches
   - ✅ PR is created automatically
   - ✅ Rescan shows improvement
   - ✅ Dashboard displays results correctly

### Mock Mode (For Development)

```bash
# Set mock mode environment variable
export MOCK_MODE=true

# This will simulate the agent loop without actual scanning/GitHub operations
```

---

## 🛠️ Tech Stack

**AI & Cloud:**
- Amazon Bedrock (Claude 3.5 Sonnet)
- Bedrock AgentCore (Custom Primitives)
- AWS Lambda (Python 3.11)
- AWS CDK (Infrastructure as Code)
- Amazon DynamoDB
- Amazon S3
- AWS API Gateway
- AWS Secrets Manager

**Frontend:**
- Next.js 15 (App Router)
- TypeScript
- shadcn/ui
- Tailwind CSS
- pnpm

**Accessibility Tools:**
- Lighthouse CI
- axe-core
- Playwright

**Integrations:**
- GitHub REST API
- Git operations

---

## 📊 Success Metrics

- ✅ **Lighthouse Score Improvement:** 10-50 point increase
- ✅ **Issues Fixed:** 80%+ resolution rate
- ✅ **Time Savings:** 95% faster than manual remediation
- ✅ **WCAG Compliance:** Meets AA standards
- ✅ **Autonomy:** Zero human intervention required

---

## 🔒 Security

- ✅ GitHub tokens stored in AWS Secrets Manager
- ✅ All API calls authenticated through API Gateway
- ✅ IAM roles follow least-privilege principle
- ✅ S3 buckets encrypted at rest
- ✅ No sensitive data in logs or reports

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🙏 Acknowledgments

- Built for the **AWS AI Agent Global Hackathon**
- Powered by **Amazon Bedrock AgentCore**
- Accessibility standards by **W3C WCAG**
- UI components by **shadcn/ui**

---

## 👥 Project Info

- **Project Type:** Autonomous AI Agent on AWS
- **Hackathon:** AWS AI Agent Global Hackathon 2025
- **Built with:** Amazon Bedrock Claude 3.5 Sonnet + AWS Lambda + ECS Fargate
- **Repository:** Clean, modular, production-ready architecture

---

## 🚧 Future Enhancements

- [ ] Support for Vue, Angular, and other frameworks
- [ ] Multi-language support (i18n)
- [ ] Scheduled recurring scans
- [ ] Slack/Email notifications
- [ ] Custom WCAG rule configuration
- [ ] Visual regression testing
- [ ] Integration with CI/CD pipelines
- [ ] Mobile app auditing
- [ ] PDF/document accessibility

---

<div align="center">

**Making the web accessible to everyone, one pull request at a time.** 🌐♿✨

Built with ❤️ using AWS Bedrock AgentCore

</div>

