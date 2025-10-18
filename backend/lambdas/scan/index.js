import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';
import { DynamoDBClient } from '@aws-sdk/client-dynamodb';
import { DynamoDBDocumentClient, UpdateCommand } from '@aws-sdk/lib-dynamodb';
import chromium from '@sparticuz/chromium';
import puppeteer from 'puppeteer-core';
import lighthouse from 'lighthouse';
import { URL } from 'url';

const s3Client = new S3Client({});
const ddbClient = new DynamoDBClient({});
const dynamodb = DynamoDBDocumentClient.from(ddbClient);

const REPORTS_BUCKET = process.env.REPORTS_BUCKET;
const PROJECTS_TABLE = process.env.PROJECTS_TABLE;

async function runLighthouseAudit(siteUrl) {
    const browser = await puppeteer.launch({
        args: chromium.args,
        defaultViewport: { width: 1920, height: 1080 },
        executablePath: await chromium.executablePath(),
        headless: chromium.headless,
        ignoreHTTPSErrors: true,
    });

    try {
        const { lhr } = await lighthouse(siteUrl, {
            port: (new URL(browser.wsEndpoint())).port,
            output: 'json',
            logLevel: 'error',
            onlyCategories: ['accessibility'],
            disableStorageReset: true,
        });

        const accessibilityScore = Math.round(lhr.categories.accessibility.score * 100);
        const audits = lhr.audits;
        
        const issues = [];
        
        for (const [auditId, audit] of Object.entries(audits)) {
            if (audit.score !== null && audit.score < 1 && audit.details && audit.details.items) {
                for (const item of audit.details.items) {
                    issues.push({
                        id: `${auditId}_${issues.length}`,
                        rule: auditId,
                        description: audit.description,
                        impact: audit.score < 0.5 ? 'critical' : audit.score < 0.9 ? 'serious' : 'moderate',
                        help: audit.title,
                        helpUrl: `https://dequeuniversity.com/rules/axe/4.4/${auditId}`,
                        selector: item.selector || item.node?.selector || 'unknown',
                        snippet: item.snippet || item.node?.snippet || '',
                        wcag: ['wcag2a', 'wcag2aa']
                    });
                }
            }
        }

        return {
            score: accessibilityScore,
            issues: issues.slice(0, 50),
            summary: {
                total: issues.length,
                critical: issues.filter(i => i.impact === 'critical').length,
                serious: issues.filter(i => i.impact === 'serious').length,
                moderate: issues.filter(i => i.impact === 'moderate').length
            }
        };
    } finally {
        await browser.close();
    }
}

export const handler = async (event) => {
    console.log('Scan Lambda invoked:', JSON.stringify(event));

    try {
        const { site_url, project_id } = event;

        if (!site_url || !project_id) {
            throw new Error('Missing required parameters: site_url and project_id');
        }

        console.log(`Running Lighthouse audit for ${site_url}...`);
        const auditResult = await runLighthouseAudit(site_url);

        const report = {
            project_id,
            site_url,
            scan_type: 'lighthouse',
            timestamp: new Date().toISOString(),
            score: auditResult.score,
            issues: auditResult.issues,
            summary: auditResult.summary
        };

        const reportKey = `${project_id}/initial_scan.json`;
        await s3Client.send(new PutObjectCommand({
            Bucket: REPORTS_BUCKET,
            Key: reportKey,
            Body: JSON.stringify(report),
            ContentType: 'application/json'
        }));

        console.log(`Scan complete. Score: ${auditResult.score}, Issues: ${auditResult.issues.length}`);

        return {
            statusCode: 200,
            body: JSON.stringify({
                project_id,
                score: auditResult.score,
                issues: auditResult.issues,
                report_url: `s3://${REPORTS_BUCKET}/${reportKey}`
            })
        };
    } catch (error) {
        console.error('Scan error:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({
                error: error.message,
                stack: error.stack
            })
        };
    }
};

