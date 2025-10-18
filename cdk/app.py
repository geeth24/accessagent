#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.storage_stack import StorageStack
from stacks.vpc_stack import VPCStack
from stacks.compute_stack import ComputeStack
from stacks.fargate_stack import AccessAgentFargateStack
from stacks.api_stack import ApiStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", "us-east-1")
)

# VPC Stack - Persistent infrastructure (deploy first, rarely changes)
vpc_stack = VPCStack(app, "AccessAgentVPCStack", env=env)

storage_stack = StorageStack(app, "AccessAgentStorageStack", env=env)
fargate_stack = AccessAgentFargateStack(app, "AccessAgentFargateStack", vpc_stack=vpc_stack, env=env)
compute_stack = ComputeStack(
    app, 
    "AccessAgentComputeStack",
    storage_stack=storage_stack,
    fargate_stack=fargate_stack,
    env=env
)
api_stack = ApiStack(
    app,
    "AccessAgentApiStack",
    compute_stack=compute_stack,
    env=env
)

app.synth()

