"""
Scan Lambda: Run real accessibility audit using Playwright + axe-core
"""

import json
import boto3
import logging
import os
from datetime import datetime
import subprocess
import tempfile

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "accessagent-projects")
S3_BUCKET = os.environ.get("S3_BUCKET")

table = dynamodb.Table(DYNAMODB_TABLE)


def run_real_accessibility_scan(site_url: str) -> dict:
    """
    Run real accessibility scan using Playwright + axe-core
    """
    try:
        from playwright.sync_api import sync_playwright
        from axe_playwright_python.sync_playwright import Axe
        
        logger.info(f"Running Playwright accessibility scan on {site_url}...")
        
        logger.info(f"Scanning {site_url} with Playwright + axe-core...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(site_url, timeout=30000, wait_until='networkidle')
                
                # Run axe-core accessibility scan
                axe = Axe()
                results = axe.run(page)
                
                # Parse violations
                violations = results.get('violations', [])
                
                issues = []
                total_violations = 0
                
                for violation in violations:
                    severity = violation.get('impact', 'moderate')
                    if severity == 'minor':
                        severity = 'moderate'
                    elif severity in ['critical', 'serious']:
                        pass
                    else:
                        severity = 'moderate'
                    
                    nodes = violation.get('nodes', [])
                    count = len(nodes)
                    total_violations += count
                    
                    snippet = nodes[0].get('html', '') if nodes else ''
                    target = nodes[0].get('target', [''])[0] if nodes else ''
                    
                    issues.append({
                        "source": "axe-core",
                        "rule": violation.get('id', ''),
                        "title": violation.get('help', ''),
                        "description": violation.get('description', ''),
                        "severity": severity,
                        "selector": target,
                        "snippet": snippet[:200],
                        "wcag": violation.get('tags', []),
                        "count": count
                    })
                
                # Calculate approximate Lighthouse score
                # Lighthouse formula: weight violations by severity
                critical_count = sum(1 for i in issues if i['severity'] == 'critical')
                serious_count = sum(1 for i in issues if i['severity'] == 'serious')
                moderate_count = sum(1 for i in issues if i['severity'] == 'moderate')
                
                # Rough Lighthouse score calculation
                deductions = (critical_count * 10) + (serious_count * 5) + (moderate_count * 2)
                lighthouse_score = max(0, min(100, 100 - deductions))
                
                browser.close()
                
                logger.info(f"Scan complete: {len(issues)} issue types, {total_violations} total violations, score: {lighthouse_score}")
                
                return {
                    "issues": issues,
                    "lighthouse_score": lighthouse_score,
                    "total_issues": total_violations,
                    "scan_type": "real"
                }
                
            except Exception as e:
                logger.error(f"Error during page scan: {str(e)}")
                browser.close()
                raise
                
    except Exception as e:
        logger.error(f"Error running accessibility scan: {str(e)}", exc_info=True)
        raise Exception(f"Real accessibility scan failed: {str(e)}")


def lambda_handler(event, context):
    """
    Main Lambda handler for accessibility scanning
    """
    logger.info(f"Scan Lambda invoked with event: {json.dumps(event)}")
    
    try:
        body = event if isinstance(event, dict) else json.loads(event.get("body", "{}"))
        site_url = body.get("site_url")
        project_id = body.get("project_id")
        
        if not site_url or not project_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "site_url and project_id are required"})
            }
        
        # Update status
        table.update_item(
            Key={"project_id": project_id},
            UpdateExpression="SET #status = :status, site_url = :url, updated_at = :timestamp",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "scanning",
                ":url": site_url,
                ":timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Get scan results (real scan with fallback to mock)
        logger.info(f"Scanning {site_url}...")
        scan_data = run_real_accessibility_scan(site_url)
        
        issues = scan_data["issues"]
        lighthouse_score = scan_data["lighthouse_score"]
        
        # Create full report
        report = {
            "project_id": project_id,
            "site_url": site_url,
            "timestamp": datetime.utcnow().isoformat(),
            "lighthouse_score": lighthouse_score,
            "total_issues": scan_data.get("total_issues", len(issues)),
            "issues": issues,
            "scan_type": scan_data.get("scan_type", "unknown")
        }
        
        # Store in S3
        report_key = f"raw/{project_id}/report.json"
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=report_key,
            Body=json.dumps(report),
            ContentType="application/json"
        )
        
        # Update DynamoDB
        table.update_item(
            Key={"project_id": project_id},
            UpdateExpression="SET #status = :status, score_before = :score, issues_found = :issues, report_url = :url",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "scanned",
                ":score": lighthouse_score,
                ":issues": len(issues),
                ":url": f"s3://{S3_BUCKET}/{report_key}"
            }
        )
        
        logger.info(f"Scan completed. Found {len(issues)} issues. Lighthouse score: {lighthouse_score}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "project_id": project_id,
                "lighthouse_score": lighthouse_score,
                "total_issues": len(issues),
                "issues": issues,
                "report_url": f"s3://{S3_BUCKET}/{report_key}"
            })
        }
        
    except Exception as e:
        logger.error(f"Error in scan handler: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
