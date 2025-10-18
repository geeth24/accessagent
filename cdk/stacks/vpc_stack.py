"""
VPC Stack - Persistent infrastructure (rarely changes)
Separate stack so Fargate updates don't recreate VPC
"""
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    CfnOutput,
)
from constructs import Construct


class VPCStack(Stack):
    """
    VPC infrastructure - should be persistent
    Separating from Fargate allows faster Fargate updates
    """
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # VPC with public subnets (for Fargate with internet access)
        self.vpc = ec2.Vpc(self, "AccessAgentVPC",
            max_azs=2,
            nat_gateways=0,  # Use public subnets to save cost
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                )
            ]
        )
        
        # Security group for VPC endpoints
        self.endpoint_sg = ec2.SecurityGroup(self, "VPCEndpointSG",
            vpc=self.vpc,
            description="Security group for VPC endpoints",
            allow_all_outbound=True
        )
        
        # Allow HTTPS from VPC
        self.endpoint_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="Allow HTTPS from VPC"
        )
        
        # Security group for Fargate tasks
        self.task_sg = ec2.SecurityGroup(self, "TaskSecurityGroup",
            vpc=self.vpc,
            description="Security group for Fargate tasks",
            allow_all_outbound=True
        )
        
        # VPC Endpoints for private AWS service access
        # S3 Gateway Endpoint (free)
        self.vpc.add_gateway_endpoint("S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3
        )
        
        # ECR API Endpoint
        self.vpc.add_interface_endpoint("ECREndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR,
            security_groups=[self.endpoint_sg]
        )
        
        # ECR Docker Endpoint
        self.vpc.add_interface_endpoint("ECRDockerEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            security_groups=[self.endpoint_sg]
        )
        
        # CloudWatch Logs Endpoint
        self.vpc.add_interface_endpoint("CloudWatchLogsEndpoint",
            service=ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            security_groups=[self.endpoint_sg]
        )
        
        # Outputs
        CfnOutput(self, "VPCId",
            value=self.vpc.vpc_id,
            description="VPC ID",
            export_name="AccessAgentVPCId"
        )
        
        CfnOutput(self, "TaskSecurityGroupId",
            value=self.task_sg.security_group_id,
            description="Task Security Group ID",
            export_name="AccessAgentTaskSGId"
        )

