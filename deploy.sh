#!/bin/bash

set -e

echo "🚀 AccessAgent Deployment Script"
echo "================================="

if [ ! -d ".venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv .venv
fi

echo "🔧 Activating virtual environment..."
source .venv/bin/activate

echo "📥 Installing CDK dependencies..."
cd cdk
pip install -q -r requirements.txt

echo "☁️  Checking AWS credentials..."
aws sts get-caller-identity > /dev/null || {
    echo "❌ AWS credentials not configured. Please run 'aws configure'"
    exit 1
}

echo "🔍 Checking if CDK is bootstrapped..."
if ! aws cloudformation describe-stacks --stack-name CDKToolkit > /dev/null 2>&1; then
    echo "🎬 Bootstrapping CDK..."
    cdk bootstrap
else
    echo "✅ CDK already bootstrapped"
fi

echo "🏗️  Deploying infrastructure..."
cdk deploy --all --require-approval never

echo ""
echo "✅ Backend deployment complete!"
echo ""
echo "📝 Next steps:"
echo "1. Copy the API Gateway URL from the outputs above"
echo "2. Update frontend/.env.local with: NEXT_PUBLIC_API_URL=<your-api-url>"
echo "3. Create a GitHub token and store it:"
echo "   aws secretsmanager create-secret --name accessagent/github-token --secret-string '{\"token\":\"your_token\"}'"
echo "4. Deploy the frontend: cd frontend && pnpm install && pnpm build"
echo ""
echo "🎉 Ready to fix accessibility issues!"

