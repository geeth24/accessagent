# GitHub Actions AWS Deployment Setup

This guide will help you set up automated CDK deployments via GitHub Actions.

## Prerequisites

- AWS CLI configured with admin access
- GitHub repository: `geeth24/accessagent`

## Setup Steps

### 1. Create OIDC Provider for GitHub Actions (One-time setup)

Run this command to create the OIDC provider if it doesn't exist:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

**Note:** If the provider already exists, you'll get an error - that's okay!

### 2. Create IAM Role for GitHub Actions

Create a file `github-actions-trust-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::081762640508:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:geeth24/accessagent:*"
        }
      }
    }
  ]
}
```

Create the role:

```bash
aws iam create-role \
  --role-name GitHubActionsCDKDeployRole \
  --assume-role-policy-document file://github-actions-trust-policy.json \
  --description "Role for GitHub Actions to deploy CDK stacks"
```

### 3. Attach Required Policies

Attach the necessary permissions (use admin for simplicity, or create a more restrictive policy):

```bash
# For full deployment access
aws iam attach-role-policy \
  --role-name GitHubActionsCDKDeployRole \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

**Or create a more restrictive policy** (recommended for production):

```bash
aws iam create-policy \
  --policy-name CDKDeploymentPolicy \
  --policy-document file://cdk-deploy-policy.json

aws iam attach-role-policy \
  --role-name GitHubActionsCDKDeployRole \
  --policy-arn arn:aws:iam::081762640508:policy/CDKDeploymentPolicy
```

### 4. Get the Role ARN

```bash
aws iam get-role --role-name GitHubActionsCDKDeployRole --query 'Role.Arn' --output text
```

This will output something like:
```
arn:aws:iam::081762640508:role/GitHubActionsCDKDeployRole
```

### 5. Add Secret to GitHub Repository

1. Go to: https://github.com/geeth24/accessagent/settings/secrets/actions
2. Click "New repository secret"
3. Name: `AWS_DEPLOY_ROLE_ARN`
4. Value: The ARN from step 4
5. Click "Add secret"

### 6. Bootstrap CDK (if not already done)

```bash
cd cdk
cdk bootstrap aws://081762640508/us-east-1
```

## Testing the Workflow

1. Make a change to any file in `cdk/` or `backend/`
2. Commit and push to main:
   ```bash
   git add .
   git commit -m "Test CDK deployment workflow"
   git push origin main
   ```
3. Check the Actions tab in GitHub to see the deployment progress

## Workflow Features

- ✅ **Automatic deployment** when changes are pushed to `cdk/` or `backend/` directories
- ✅ **Manual trigger** available via workflow_dispatch
- ✅ **CDK diff** shown before deployment
- ✅ **Secure** using OIDC (no long-lived credentials)
- ✅ **Fast** with dependency caching

## Troubleshooting

### Deployment fails with permissions error
- Check that the role has the necessary permissions
- Verify the trust policy allows your repository

### OIDC provider not found
- Run the OIDC provider creation command from step 1

### Secret not found
- Verify you added `AWS_DEPLOY_ROLE_ARN` to GitHub repository secrets
- Check the secret name matches exactly (case-sensitive)

