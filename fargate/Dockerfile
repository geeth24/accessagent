# Explicitly use AMD64 architecture for AWS Fargate (rebuilt: 2025-10-18 v4 REAL GIT CONFIG)
FROM --platform=linux/amd64 node:20-alpine

# Install Python, git, and build essentials
RUN apk add --no-cache \
    python3 \
    py3-pip \
    git \
    bash \
    curl

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Set up Python environment
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Copy agent code
COPY *.py ./

# Set up workspace directory for repo clones
RUN mkdir -p /workspace
WORKDIR /workspace

# Run the NEW agentic agent (AI runs inside Fargate with full codebase access)
CMD ["python3", "/app/agent_agentic.py"]

