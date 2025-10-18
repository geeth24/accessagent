from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
    CfnOutput,
)
from constructs import Construct
import os

class ComputeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        storage_stack,
        fargate_stack=None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Import existing secret instead of creating it
        self.github_token_secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "GitHubTokenSecret",
            secret_name="accessagent/github-token"
        )

        lambda_role = iam.Role(
            self,
            "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
        )

        storage_stack.projects_table.grant_read_write_data(lambda_role)
        storage_stack.reports_bucket.grant_read_write(lambda_role)
        self.github_token_secret.grant_read(lambda_role)

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=[
                    # Allow all Claude models across all regions (inference profiles route cross-region)
                    f"arn:aws:bedrock:*:{self.account}:inference-profile/*",
                    "arn:aws:bedrock:*::foundation-model/anthropic.*"
                ],
            )
        )

        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[f"arn:aws:lambda:{self.region}:{self.account}:function:accessagent-*"],
            )
        )
        
        # Add ECS permissions for agent orchestrator to trigger Fargate tasks
        if fargate_stack:
            lambda_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ecs:RunTask",
                        "ecs:DescribeTasks",
                    ],
                    resources=["*"],
                )
            )
            lambda_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["iam:PassRole"],
                    resources=[
                        fargate_stack.task_definition.task_role.role_arn,
                        fargate_stack.task_definition.execution_role.role_arn,
                    ],
                )
            )
            lambda_role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "ec2:DescribeSubnets",
                        "ec2:DescribeVpcs",
                    ],
                    resources=["*"],
                )
            )

        common_environment = {
            "DYNAMODB_TABLE": storage_stack.projects_table.table_name,
            "S3_BUCKET": storage_stack.reports_bucket.bucket_name,
            "GITHUB_TOKEN_SECRET_NAME": self.github_token_secret.secret_name,
        }
        
        # Add Fargate environment variables if available
        if fargate_stack:
            common_environment["ECS_CLUSTER"] = fargate_stack.cluster.cluster_name
            # Use family name instead of ARN to avoid CloudFormation export conflicts
            # ECS will automatically use the latest revision
            common_environment["ECS_TASK_DEFINITION"] = fargate_stack.task_definition.family
            common_environment["ECS_SECURITY_GROUP"] = fargate_stack.task_security_group.security_group_id
            # VPC and subnets will be auto-detected by Lambda from cluster

        self.agent_orchestrator = lambda_.Function(
            self,
            "AgentOrchestrator",
            function_name="accessagent-agent-orchestrator",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("../backend/lambdas/agent_orchestrator"),
            role=lambda_role,
            timeout=Duration.minutes(15),
            memory_size=1024,
            environment=common_environment,
        )

        self.scan_function = lambda_.Function(
            self,
            "ScanFunction",
            function_name="accessagent-scan",
            runtime=lambda_.Runtime.NODEJS_18_X,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                "../backend/lambdas/scan",
                bundling=lambda_.BundlingOptions(
                    image=lambda_.Runtime.NODEJS_18_X.bundling_image,
                    command=[
                        "bash", "-c",
                        "npm install && cp -r . /asset-output/"
                    ],
                    user="root"
                )
            ),
            role=lambda_role,
            timeout=Duration.minutes(5),
            memory_size=2048,
            environment={
                **common_environment,
                "PROJECTS_TABLE": storage_stack.projects_table.table_name,
                "REPORTS_BUCKET": storage_stack.reports_bucket.bucket_name,
            },
        )

        CfnOutput(
            self,
            "AgentOrchestratorArn",
            value=self.agent_orchestrator.function_arn,
            export_name="AccessAgentAgentOrchestratorArn"
        )
        
        CfnOutput(
            self,
            "ScanFunctionArn",
            value=self.scan_function.function_arn,
            export_name="AccessAgentScanFunctionArn"
        )

