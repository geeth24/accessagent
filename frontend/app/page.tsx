"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  Loader2, 
  CheckCircle2, 
  AlertCircle, 
  ExternalLink, 
  GitPullRequest,
  Activity,
  Bug,
  TrendingUp,
  Sparkles
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { GitHubRepoPicker } from "@/components/github-repo-picker";
import { toast } from "sonner";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod";

interface ActivityLogEntry {
  timestamp: string;
  step: string;
  message: string;
}

interface Issue {
  id: string;
  rule: string;
  description: string;
  impact: string;
  help: string;
  helpUrl: string;
  selector: string;
  snippet: string;
  wcag: string[];
}

interface ProjectData {
  project_id: string;
  status: string;
  progress: string;
  current_step: string;
  repo_url: string;
  site_url: string;
  activity_log?: ActivityLogEntry[];
  pr_url?: string;
  pr_number?: string;
  framework?: string;
  issues?: Issue[];
  initial_score?: number;
  improvement?: {
    score_before?: number;
    score_after?: number;
    score_delta?: number;
    issues_fixed?: number;
    improvement_summary?: string;
  };
}

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("");
  const [siteUrl, setSiteUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [projectData, setProjectData] = useState<ProjectData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [useRepoPicker, setUseRepoPicker] = useState(true);

  const pollProject = async (projectId: string) => {
    try {
      const response = await fetch(`${API_URL}/project/${projectId}`);
      if (!response.ok) {
        throw new Error("Failed to fetch project status");
      }
      const data = await response.json();
      setProjectData(data);

      if (data.status === "processing" && parseInt(data.progress) < 100) {
        setTimeout(() => pollProject(projectId), 2000);
      }
    } catch (err) {
      console.error("Polling error:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch status");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    setProjectData(null);

    try {
      const response = await fetch(`${API_URL}/scan`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          repo_url: repoUrl,
          site_url: siteUrl,
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to start scan: ${response.statusText}`);
      }

      const data = await response.json();
      toast.success("Scan started!", {
        description: "Analyzing your website for accessibility issues...",
      });
      
      setProjectData(data);
      pollProject(data.project_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      toast.error("Error", {
        description: err instanceof Error ? err.message : "Failed to start scan",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const getImpactColor = (impact: string) => {
    switch (impact) {
      case "critical": return "destructive";
      case "serious": return "destructive";
      case "moderate": return "default";
      case "minor": return "secondary";
      default: return "default";
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <nav className="border-b">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold">AccessAgent</h1>
          </div>
          <ThemeToggle />
        </div>
      </nav>

      <main className="container mx-auto px-4 py-12 max-w-5xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4">
              Autonomous Accessibility Fixes
            </h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              AI-powered agent that scans your website, identifies accessibility issues,
              and automatically creates pull requests with fixes.
            </p>
          </div>

          <Card className="mb-8">
            <CardHeader>
              <CardTitle>Start a New Scan</CardTitle>
              <CardDescription>
                Enter your repository and website URL to begin the accessibility audit
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="repo-url">GitHub Repository URL</Label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setUseRepoPicker(!useRepoPicker)}
                      disabled={isSubmitting}
                    >
                      {useRepoPicker ? "Enter manually" : "Pick from GitHub"}
                    </Button>
                  </div>
                  {useRepoPicker ? (
                    <GitHubRepoPicker
                      value={repoUrl}
                      onSelect={setRepoUrl}
                      disabled={isSubmitting}
                    />
                  ) : (
                    <Input
                      id="repo-url"
                      type="url"
                      placeholder="https://github.com/username/repo"
                      value={repoUrl}
                      onChange={(e) => setRepoUrl(e.target.value)}
                      required
                      disabled={isSubmitting}
                    />
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="site-url">Live Website URL</Label>
                  <Input
                    id="site-url"
                    type="url"
                    placeholder="https://example.com"
                    value={siteUrl}
                    onChange={(e) => setSiteUrl(e.target.value)}
                    required
                    disabled={isSubmitting}
                  />
                </div>

                <Button type="submit" disabled={isSubmitting} className="w-full">
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Starting Scan...
                    </>
                  ) : (
                    <>
                      <Sparkles className="mr-2 h-4 w-4" />
                      Start Accessibility Scan
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>

          {error && (
            <Alert variant="destructive" className="mb-8">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <AnimatePresence>
            {projectData && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.3 }}
              >
                <Card>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="flex items-center gap-2">
                          {projectData.status === "completed" ? (
                            <CheckCircle2 className="h-5 w-5 text-green-500" />
                          ) : (
                            <Loader2 className="h-5 w-5 animate-spin text-primary" />
                          )}
                          {projectData.current_step || "Processing..."}
                        </CardTitle>
                        <CardDescription className="mt-2">
                          {projectData.repo_url}
                        </CardDescription>
                      </div>
                      {projectData.framework && (
                        <Badge variant="outline">{projectData.framework}</Badge>
                      )}
                    </div>
                    
                    <div className="mt-4 space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Progress</span>
                        <span className="font-medium">{projectData.progress}%</span>
                      </div>
                      <Progress value={parseInt(projectData.progress)} className="h-2" />
                    </div>
                  </CardHeader>

                  <CardContent>
                    <Tabs defaultValue="activity" className="w-full">
                      <TabsList className="grid w-full grid-cols-3">
                        <TabsTrigger value="activity">
                          <Activity className="h-4 w-4 mr-2" />
                          Activity
                        </TabsTrigger>
                        <TabsTrigger value="issues">
                          <Bug className="h-4 w-4 mr-2" />
                          Issues ({projectData.issues?.length || 0})
                        </TabsTrigger>
                        <TabsTrigger value="results" disabled={!projectData.pr_url}>
                          <TrendingUp className="h-4 w-4 mr-2" />
                          Results
                        </TabsTrigger>
                      </TabsList>

                      <TabsContent value="activity" className="mt-4">
                        <div className="space-y-4">
                          {projectData.activity_log && projectData.activity_log.length > 0 ? (
                            <div className="space-y-3">
                              {projectData.activity_log.map((log, index) => (
                                <motion.div
                                  key={index}
                                  initial={{ opacity: 0, x: -20 }}
                                  animate={{ opacity: 1, x: 0 }}
                                  transition={{ delay: index * 0.1 }}
                                  className="flex gap-3 items-start"
                                >
                                  <div className="mt-1">
                                    <div className="h-2 w-2 rounded-full bg-primary" />
                                  </div>
                                  <div className="flex-1 space-y-1">
                                    <p className="text-sm font-medium">{log.step}</p>
                                    <p className="text-sm text-muted-foreground">{log.message}</p>
                                    <p className="text-xs text-muted-foreground">
                                      {new Date(log.timestamp).toLocaleTimeString()}
                                    </p>
                                  </div>
                                </motion.div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-center text-muted-foreground py-8">
                              No activity logs yet
                            </p>
                          )}
                        </div>
                      </TabsContent>

                      <TabsContent value="issues" className="mt-4">
                        <div className="space-y-4">
                          {projectData.issues && projectData.issues.length > 0 ? (
                            <>
                              {projectData.initial_score !== undefined && (
                                <Alert>
                                  <TrendingUp className="h-4 w-4" />
                                  <AlertDescription>
                                    Initial accessibility score: <strong>{projectData.initial_score}/100</strong>
                                  </AlertDescription>
                                </Alert>
                              )}
                              <div className="space-y-3">
                                {projectData.issues.map((issue) => (
                                  <Card key={issue.id}>
                                    <CardHeader className="pb-3">
                                      <div className="flex items-start justify-between gap-4">
                                        <div className="flex-1">
                                          <CardTitle className="text-base">{issue.help}</CardTitle>
                                          <CardDescription className="mt-1">
                                            {issue.description}
                                          </CardDescription>
                                        </div>
                                        <Badge variant={getImpactColor(issue.impact)}>
                                          {issue.impact}
                                        </Badge>
                                      </div>
                                    </CardHeader>
                                    <CardContent className="pt-0">
                                      <div className="space-y-2 text-sm">
                                        <div>
                                          <span className="font-medium">Selector:</span>
                                          <code className="ml-2 text-xs bg-muted px-2 py-1 rounded">
                                            {issue.selector}
                                          </code>
                                        </div>
                                        <div>
                                          <span className="font-medium">WCAG:</span>
                                          <span className="ml-2 text-muted-foreground">
                                            {issue.wcag.join(", ")}
                                          </span>
                                        </div>
                                        <a
                                          href={issue.helpUrl}
          target="_blank"
          rel="noopener noreferrer"
                                          className="inline-flex items-center text-primary hover:underline"
                                        >
                                          Learn more
                                          <ExternalLink className="ml-1 h-3 w-3" />
                                        </a>
                                      </div>
                                    </CardContent>
                                  </Card>
                                ))}
                              </div>
                            </>
                          ) : (
                            <p className="text-center text-muted-foreground py-8">
                              No issues detected yet
                            </p>
                          )}
                        </div>
                      </TabsContent>

                      <TabsContent value="results" className="mt-4">
                        <div className="space-y-4">
                          {projectData.pr_url && (
                            <>
                              <Alert>
                                <GitPullRequest className="h-4 w-4" />
                                <AlertDescription>
                                  Pull request created successfully! Review the changes and merge when ready.
                                </AlertDescription>
                              </Alert>

                              <Card>
                                <CardHeader>
                                  <CardTitle>Pull Request</CardTitle>
                                  <CardDescription>
                                    PR #{projectData.pr_number}
                                  </CardDescription>
                                </CardHeader>
                                <CardContent>
                                  <Button asChild className="w-full">
                                    <a
                                      href={projectData.pr_url}
          target="_blank"
          rel="noopener noreferrer"
        >
                                      <ExternalLink className="mr-2 h-4 w-4" />
                                      View Pull Request
                                    </a>
                                  </Button>
                                </CardContent>
                              </Card>

                              {projectData.improvement && (
                                <Card>
                                  <CardHeader>
                                    <CardTitle>Improvement Summary</CardTitle>
                                  </CardHeader>
                                  <CardContent className="space-y-4">
                                    {projectData.improvement.score_before !== undefined && (
                                      <div className="grid grid-cols-3 gap-4 text-center">
                                        <div>
                                          <p className="text-2xl font-bold">
                                            {projectData.improvement.score_before}
                                          </p>
                                          <p className="text-sm text-muted-foreground">Before</p>
                                        </div>
                                        <div>
                                          <p className="text-2xl font-bold text-primary">
                                            +{projectData.improvement.score_delta || 0}
                                          </p>
                                          <p className="text-sm text-muted-foreground">Improvement</p>
                                        </div>
                                        <div>
                                          <p className="text-2xl font-bold text-green-500">
                                            {projectData.improvement.score_after}
                                          </p>
                                          <p className="text-sm text-muted-foreground">After</p>
                                        </div>
                                      </div>
                                    )}
                                    {projectData.improvement.improvement_summary && (
                                      <p className="text-center text-muted-foreground">
                                        {projectData.improvement.improvement_summary}
                                      </p>
                                    )}
                                  </CardContent>
                                </Card>
                              )}
                            </>
                          )}
                        </div>
                      </TabsContent>
                    </Tabs>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </main>
    </div>
  );
}
