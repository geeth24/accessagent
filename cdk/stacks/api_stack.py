from aws_cdk import (
    Stack,
    Duration,
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_certificatemanager as acm,
    CfnOutput,
)
from constructs import Construct
import os

class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        compute_stack,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Custom domain - hardcoded to always use api.accessagent.geeth.app
        custom_domain_name = "api.accessagent.geeth.app"

        self.api = apigateway.RestApi(
            self,
            "AccessAgentApi",
            rest_api_name="accessagent-api",
            description="API for AccessAgent",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"],
                expose_headers=["Content-Type", "X-Amzn-RequestId"],
                allow_credentials=False,
                max_age=Duration.hours(1)
            ),
        )

        # Lambda integration
        orchestrator_integration = apigateway.LambdaIntegration(
            compute_stack.agent_orchestrator,
            proxy=True,
        )

        # POST /scan - start a new scan
        scan_resource = self.api.root.add_resource("scan")
        scan_resource.add_method("POST", orchestrator_integration)

        # GET /project/{project_id} - get project status
        project_resource = self.api.root.add_resource("project")
        project_detail_resource = project_resource.add_resource("{project_id}")
        project_detail_resource.add_method("GET", orchestrator_integration)

        # Custom domain setup - ALWAYS configured
        # Use existing wildcard certificate for *.accessagent.geeth.app
        certificate = acm.Certificate.from_certificate_arn(
            self,
            "ApiCertificate",
            certificate_arn="arn:aws:acm:us-east-1:081762640508:certificate/ace8e5b5-1775-476b-924a-8cb5ea47b524",
        )

        # Add custom domain to API Gateway
        domain = self.api.add_domain_name(
            "CustomDomain",
            domain_name=custom_domain_name,
            certificate=certificate,
            endpoint_type=apigateway.EndpointType.EDGE,
            security_policy=apigateway.SecurityPolicy.TLS_1_2
        )

        # Output the CloudFront domain to create CNAME in external DNS
        CfnOutput(
            self,
            "CustomDomainTarget",
            value=domain.domain_name_alias_domain_name,
            description=f"Add CNAME: {custom_domain_name} -> <this value> in your DNS"
        )

        CfnOutput(
            self,
            "CustomDomainUrl",
            value=f"https://{custom_domain_name}",
            export_name="AccessAgentCustomDomainUrl",
            description="Custom domain URL for AccessAgent API"
        )

        CfnOutput(
            self,
            "ApiUrl",
            value=self.api.url,
            export_name="AccessAgentApiUrl"
        )

        CfnOutput(
            self,
            "ApiId",
            value=self.api.rest_api_id,
            export_name="AccessAgentApiId"
        )
