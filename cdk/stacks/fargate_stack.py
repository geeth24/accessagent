"""
CDK Stack for ECS Fargate Agent
"""

from aws_cdk import (
    Stack,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_ecr_assets as ecr_assets,
    aws_logs as logs,
    Duration,
)
from constructs import Construct
import os


class AccessAgentFargateStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get environment variables
        projects_table_name = os.environ.get("PROJECTS_TABLE", "accessagent-projects")
        
        # Use VPC from separate VPC stack
        vpc = vpc_stack.vpc
        task_sg = vpc_stack.task_sg
        
        # Store security group for export
        self.task_security_group = task_sg
        
        # Create ECS Cluster
        cluster = ecs.Cluster(self, "AccessAgentCluster",
            vpc=vpc,
            cluster_name="accessagent-cluster"
        )
        
        # Build Docker image
        image_asset = ecr_assets.DockerImageAsset(self, "AgentImage",
            directory=os.path.join(os.path.dirname(__file__), "../../fargate")
        )
        
        # Create task execution role
        execution_role = iam.Role(self, "AgentExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ]
        )
        
        # Create task role with necessary permissions
        task_role = iam.Role(self, "AgentTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )
        
        # Grant permissions to task role
        task_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "dynamodb:GetItem",
                "dynamodb:UpdateItem",
                "dynamodb:PutItem"
            ],
            resources=[f"arn:aws:dynamodb:{self.region}:{self.account}:table/{projects_table_name}"]
        ))
        
        task_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "secretsmanager:GetSecretValue"
            ],
            resources=[f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:accessagent/*"]
        ))
        
        task_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock:InvokeModel"
            ],
            resources=["*"]
        ))
        
        # Create task definition
        task_definition = ecs.FargateTaskDefinition(self, "AgentTask",
            memory_limit_mib=2048,  # 2GB RAM
            cpu=512,  # 0.5 vCPU
            execution_role=execution_role,
            task_role=task_role
        )
        
        # Add container
        container = task_definition.add_container("AgentContainer",
            image=ecs.ContainerImage.from_docker_image_asset(image_asset),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="accessagent",
                log_retention=logs.RetentionDays.ONE_WEEK
            ),
            environment={
                "DYNAMODB_TABLE": projects_table_name,
                "AWS_REGION": self.region
            }
        )
        
        # Export cluster and task definition ARNs for use in other stacks
        self.cluster = cluster
        self.task_definition = task_definition
        self.vpc = vpc
        
        # Store ARNs as stack outputs
        from aws_cdk import CfnOutput
        
        CfnOutput(self, "ClusterArn",
            value=cluster.cluster_arn,
            description="ECS Cluster ARN"
        )
        
        CfnOutput(self, "TaskDefinitionArn",
            value=task_definition.task_definition_arn,
            description="Fargate Task Definition ARN"
            # No export - pass directly to ComputeStack
        )
        
        CfnOutput(self, "TaskSecurityGroupId",
            value=task_sg.security_group_id,
            description="Security Group ID for Fargate tasks"
            # No export - pass directly to ComputeStack
        )

