from aws_cdk import (
    Stack,
    aws_dynamodb as dynamodb,
    aws_s3 as s3,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

class StorageStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.projects_table = dynamodb.Table(
            self,
            "ProjectsTable",
            table_name="accessagent-projects",
            partition_key=dynamodb.Attribute(
                name="project_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.reports_bucket = s3.Bucket(
            self,
            "ReportsBucket",
            bucket_name=f"accessagent-reports-{self.account}",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.HEAD],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3000,
                )
            ],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        CfnOutput(
            self,
            "ProjectsTableName",
            value=self.projects_table.table_name,
            export_name="AccessAgentProjectsTableName"
        )

        CfnOutput(
            self,
            "ReportsBucketName",
            value=self.reports_bucket.bucket_name,
            export_name="AccessAgentReportsBucketName"
        )

