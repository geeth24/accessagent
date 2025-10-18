#!/bin/bash

set -e

ACCOUNT_ID="081762640508"
REPO="geeth24/accessagent"
ROLE_NAME="GitHubActionsCDKDeployRole"
REGION="us-east-1"

echo "🚀 Setting up GitHub Actions deployment for AccessAgent"
echo ""

# Step 1: Create OIDC Provider (if it doesn't exist)
echo "📝 Step 1: Creating OIDC Provider for GitHub Actions..."
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  2>/dev/null || echo "✓ OIDC Provider already exists"

echo ""

# Step 2: Create trust policy
echo "📝 Step 2: Creating trust policy..."
cat > /tmp/github-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${REPO}:*"
        }
      }
    }
  ]
}
EOF

# Step 3: Create IAM role
echo "📝 Step 3: Creating IAM role..."
aws iam create-role \
  --role-name ${ROLE_NAME} \
  --assume-role-policy-document file:///tmp/github-trust-policy.json \
  --description "Role for GitHub Actions to deploy CDK stacks" \
  2>/dev/null || echo "✓ Role already exists"

echo ""

# Step 4: Attach AdministratorAccess policy (you can restrict this later)
echo "📝 Step 4: Attaching policies..."
aws iam attach-role-policy \
  --role-name ${ROLE_NAME} \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess \
  2>/dev/null || echo "✓ Policy already attached"

echo ""

# Step 5: Get role ARN
echo "📝 Step 5: Getting role ARN..."
ROLE_ARN=$(aws iam get-role --role-name ${ROLE_NAME} --query 'Role.Arn' --output text)

echo ""
echo "✅ Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 NEXT STEPS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Add this Role ARN to your GitHub repository secrets:"
echo ""
echo "   Name:  AWS_DEPLOY_ROLE_ARN"
echo "   Value: ${ROLE_ARN}"
echo ""
echo "2. Go to: https://github.com/${REPO}/settings/secrets/actions"
echo "3. Click 'New repository secret'"
echo "4. Paste the name and value above"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎉 After adding the secret, push to main to trigger deployment!"
echo ""

# Cleanup
rm /tmp/github-trust-policy.json

