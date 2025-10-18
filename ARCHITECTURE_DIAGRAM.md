# AccessAgent Architecture Diagram (Mermaid)

## Complete System Architecture

```mermaid
graph TB
    subgraph "Frontend"
        UI[Next.js Frontend<br/>Dashboard + Results]
    end
    
    subgraph "AWS Cloud"
        subgraph "API Layer"
            APIGW[API Gateway<br/>api.accessagent.geeth.app<br/>POST /scan<br/>GET /project/:id]
        end
        
        subgraph "Orchestration"
            ORCH[Agent Orchestrator Lambda<br/>Python 3.11<br/>15 min timeout]
        end
        
        subgraph "Scanning"
            SCAN[Scan Lambda<br/>Node.js 18<br/>Lighthouse + axe-core<br/>5 min timeout]
        end
        
        subgraph "Agentic AI"
            FARGATE[Fargate Container<br/>Python 3.11<br/>Claude 3.5 Sonnet<br/>2 hour max<br/><br/>1. Read issues from DB<br/>2. Clone repository<br/>3. Read full codebase<br/>4. AI generates fixes<br/>5. Apply fixes<br/>6. Build project<br/>7. Iterate if needed<br/>8. Create PR]
        end
        
        subgraph "Storage"
            DDB[(DynamoDB<br/>accessagent-projects)]
            S3[(S3 Bucket<br/>Reports & Scans)]
            SECRETS[Secrets Manager<br/>GitHub Token]
        end
        
        subgraph "AI Service"
            BEDROCK[Amazon Bedrock<br/>Claude 3.5 Sonnet v2<br/>Code Analysis<br/>Fix Generation]
        end
    end
    
    subgraph "External"
        GITHUB[GitHub API<br/>Clone<br/>Branch<br/>Commit<br/>PR]
    end
    
    UI -->|HTTPS| APIGW
    APIGW -->|Invoke| ORCH
    ORCH -->|Invoke| SCAN
    ORCH -->|Trigger ECS Task| FARGATE
    ORCH -->|Store| DDB
    
    SCAN -->|Parse Issues| DDB
    SCAN -->|Upload Report| S3
    
    FARGATE -->|Read Issues| DDB
    FARGATE -->|Store Results| DDB
    FARGATE -->|Read Report| S3
    FARGATE -->|Read Token| SECRETS
    FARGATE -->|Generate Fixes| BEDROCK
    FARGATE -->|Git Operations| GITHUB
    
    UI -.->|Poll Status| APIGW
    
    style UI fill:#e1f5ff
    style APIGW fill:#fff4e6
    style ORCH fill:#ffe6f0
    style SCAN fill:#e6f3ff
    style FARGATE fill:#f0e6ff
    style DDB fill:#e8f5e9
    style S3 fill:#e8f5e9
    style SECRETS fill:#e8f5e9
    style BEDROCK fill:#fff9c4
    style GITHUB fill:#f5f5f5
```

## Infrastructure Stacks (CDK)

```mermaid
graph LR
    subgraph "CDK Deployment"
        VPC[VPC Stack<br/>Persistent<br/>VPC + Endpoints<br/>Security Groups]
        STORAGE[Storage Stack<br/>DynamoDB<br/>S3 Bucket]
        FARGATE_STK[Fargate Stack<br/>ECS Cluster<br/>Task Definition<br/>Container Image]
        COMPUTE[Compute Stack<br/>2 Lambda Functions<br/>IAM Roles]
        API[API Stack<br/>API Gateway<br/>Custom Domain<br/>Integrations]
    end
    
    VPC -->|Provides| FARGATE_STK
    STORAGE -->|Used by| COMPUTE
    STORAGE -->|Used by| FARGATE_STK
    FARGATE_STK -->|Invoked by| COMPUTE
    COMPUTE -->|Integrated with| API
    
    style VPC fill:#e3f2fd
    style STORAGE fill:#e8f5e9
    style FARGATE_STK fill:#f3e5f5
    style COMPUTE fill:#fff9c4
    style API fill:#fce4ec
```

## Detailed Data Flow

```mermaid
sequenceDiagram
    actor User
    participant UI as Next.js Frontend
    participant API as API Gateway
    participant Orch as Agent Orchestrator
    participant Scan as Scan Lambda
    participant DB as DynamoDB
    participant S3 as S3 Bucket
    participant Fargate as Fargate Agent
    participant Bedrock as Amazon Bedrock
    participant GitHub as GitHub API
    
    User->>UI: Enter site URL & repo URL
    UI->>API: POST /scan
    API->>Orch: Invoke Lambda
    Orch->>DB: Create project (status: initialized)
    Orch->>Scan: Invoke Lighthouse scan
    Scan->>Scan: Run Lighthouse + axe-core
    Scan->>S3: Upload full report
    Scan->>DB: Save issues
    Scan-->>Orch: Return issues
    Orch->>Fargate: Trigger ECS Task (async)
    Orch-->>API: Return project_id
    API-->>UI: 200 OK with project_id
    UI->>User: Show "Scan in progress..."
    
    Note over Fargate: Fargate runs autonomously
    Fargate->>DB: Read issues
    Fargate->>GitHub: Clone repository
    Fargate->>Fargate: Read entire codebase
    Fargate->>Bedrock: Analyze code + issues
    Bedrock-->>Fargate: Generate fixes
    Fargate->>Fargate: Apply fixes
    Fargate->>Fargate: Run build
    
    alt Build passes
        Fargate->>GitHub: Create branch & commit
        Fargate->>GitHub: Open PR
        Fargate->>DB: Update (status: completed)
    else Build fails
        Fargate->>Bedrock: Analyze build errors
        Bedrock-->>Fargate: Generate new fixes
        Note over Fargate: Iterate up to 5 times
    end
    
    loop Poll for status
        UI->>API: GET /project/:id
        API->>Orch: Invoke Lambda
        Orch->>DB: Read project
        DB-->>Orch: Project data
        Orch-->>API: Project status
        API-->>UI: Status update
    end
    
    UI->>User: Show PR link & results
```

## Component Interaction

```mermaid
graph TB
    subgraph "Request Flow"
        A[User Request] --> B[API Gateway]
        B --> C{Agent Orchestrator}
        C -->|Sync| D[Scan Lambda]
        C -->|Async| E[Fargate Agent]
    end
    
    subgraph "Scan Process"
        D --> F[Lighthouse CI]
        D --> G[axe-core]
        F --> H[Parse Results]
        G --> H
        H --> I[(DynamoDB)]
        H --> J[(S3)]
    end
    
    subgraph "Agentic Loop"
        E --> K[Read Issues from DB]
        K --> L[Clone Full Repo]
        L --> M[Read Codebase]
        M --> N{AI Analysis}
        N -->|Bedrock| O[Generate Fixes]
        O --> P[Apply Patches]
        P --> Q{Build Project}
        Q -->|Fail| N
        Q -->|Pass| R[Create PR]
        R --> S[GitHub API]
    end
    
    subgraph "Storage"
        I
        J
        T[Secrets Manager]
    end
    
    E -.->|Read Token| T
    C -.->|Store State| I
    
    style A fill:#e1f5ff
    style C fill:#ffe6f0
    style D fill:#e6f3ff
    style E fill:#f0e6ff
    style N fill:#fff9c4
    style I fill:#e8f5e9
    style J fill:#e8f5e9
    style T fill:#e8f5e9
```

## Simplified Architecture

```mermaid
flowchart LR
    User[👤 User] -->|Submit URL| Frontend[🎨 Frontend]
    Frontend -->|REST API| API[🌐 API Gateway]
    API -->|Invoke| Orch[⚡ Orchestrator]
    
    Orch -->|Scan| Scan[🔍 Scan Lambda]
    Orch -->|Trigger| Fargate[🤖 Fargate AI Agent]
    
    Scan -->|Issues| DB[(💾 DynamoDB)]
    Scan -->|Report| S3[(📦 S3)]
    
    Fargate -->|Read| DB
    Fargate -->|AI| Bedrock[🧠 Bedrock Claude]
    Fargate -->|PR| GitHub[📝 GitHub]
    
    Frontend -.->|Poll| API
    
    style User fill:#e1f5ff
    style Frontend fill:#e1f5ff
    style API fill:#fff4e6
    style Orch fill:#ffe6f0
    style Scan fill:#e6f3ff
    style Fargate fill:#f0e6ff
    style DB fill:#e8f5e9
    style S3 fill:#e8f5e9
    style Bedrock fill:#fff9c4
    style GitHub fill:#f5f5f5
```

## Key Architecture Benefits

```mermaid
mindmap
  root((AccessAgent<br/>Architecture))
    Monolithic Fargate
      Full codebase context
      Iterative build-fix loop
      No cold starts
      Better AI decisions
    Separate VPC Stack
      Persistent infrastructure
      5-10 min faster updates
      Cost savings
      Best practice
    Simplified Lambdas
      2 instead of 4
      40% less code
      Easier maintenance
      Lower costs
    Storage Layer
      DynamoDB for state
      S3 for reports
      Secrets Manager
      On-demand scaling
```

## Cost Breakdown

```mermaid
pie title "Cost Per Scan (~$0.28)"
    "Fargate (30 min)" : 0.10
    "Bedrock Tokens" : 0.15
    "Scan Lambda" : 0.01
    "Orchestrator" : 0.005
    "DynamoDB" : 0.01
    "S3" : 0.001
```

---

## Usage

These diagrams can be:
- **Embedded in README.md** (GitHub renders Mermaid)
- **Exported as images** using Mermaid Live Editor
- **Included in presentations** for the hackathon
- **Added to DevPost submission** for judges

## Tools

- **Mermaid Live Editor:** https://mermaid.live
- **VS Code Extension:** Markdown Preview Mermaid Support
- **GitHub:** Native Mermaid rendering in markdown files

---

**Built for AWS AI Agent Global Hackathon 2025**

