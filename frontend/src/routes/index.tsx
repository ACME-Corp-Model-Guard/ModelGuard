import { createFileRoute } from "@tanstack/react-router";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Link } from "@tanstack/react-router";
import {
  Activity,
  Database,
  Code,
  Upload,
  Search,
  Network,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { fetchHealth, listArtifacts } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

export const Route = createFileRoute("/")({ component: ProtectedDashboard });

function ProtectedDashboard() {
  const auth = useAuth();

  if (auth.isLoading) {
    return (
      <div
        className="flex items-center justify-center min-h-screen"
        role="status"
        aria-live="polite"
      >
        <Loader2
          className="h-8 w-8 animate-spin text-primary"
          aria-hidden="true"
        />
        <span className="sr-only">Loading...</span>
      </div>
    );
  }

  if (auth.error) {
    return (
      <div className="p-6" role="alert">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Authentication Error</AlertTitle>
          <AlertDescription>{auth.error.message}</AlertDescription>
        </Alert>
      </div>
    );
  }

  // Redirect to Cognito login if not authenticated
  if (!auth.isAuthenticated) {
    auth.signinRedirect();
    return (
      <div
        className="flex items-center justify-center min-h-screen"
        role="status"
        aria-live="polite"
      >
        <p>Redirecting to login...</p>
      </div>
    );
  }

  return <Dashboard token={auth.user?.id_token} />;
}

function Dashboard({ token }: { token?: string }) {
  const [modelCount, setModelCount] = useState<number>(0);
  const [datasetCount, setDatasetCount] = useState<number>(0);
  const [codeCount, setCodeCount] = useState<number>(0);
  const [artifactCount, setArtifactCount] = useState<number>(0);
  const [healthStatus, setHealthStatus] = useState<string>("Unknown");
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setIsLoading(true);
        setError(null);

        // Health check
        try {
          const health = await fetchHealth(token);
          setHealthStatus(health.status || "OK");
        } catch (e) {
          setHealthStatus("Degraded");
        }

        // Fetch artifacts
        const artifacts = await listArtifacts([{ name: "*" }], token);
        setArtifactCount(artifacts.length);
        setModelCount(
          artifacts.filter((a) => a.artifact_type === "model").length,
        );
        setDatasetCount(
          artifacts.filter((a) => a.artifact_type === "dataset").length,
        );
        setCodeCount(
          artifacts.filter((a) => a.artifact_type === "code").length,
        );
      } catch (e) {
        setError(
          e instanceof Error ? e.message : "Failed to load dashboard data",
        );
        setHealthStatus("Offline");
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [token]);

  const getHealthColor = (status: string) => {
    switch (status) {
      case "OK":
        return "text-green-600 dark:text-green-400";
      case "Degraded":
        return "text-yellow-600 dark:text-yellow-400";
      default:
        return "text-red-600 dark:text-red-400";
    }
  };

  const getHealthIcon = (status: string) => {
    switch (status) {
      case "OK":
        return (
          <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
        );
      case "Degraded":
        return (
          <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
        );
      default:
        return (
          <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
        );
    }
  };

  if (isLoading) {
    return (
      <div
        className="flex items-center justify-center min-h-[60vh]"
        role="status"
        aria-live="polite"
      >
        <Loader2
          className="h-8 w-8 animate-spin text-primary"
          aria-hidden="true"
        />
        <span className="sr-only">Loading dashboard...</span>
      </div>
    );
  }

  return (
    <main className="container mx-auto p-6 space-y-8" role="main">
      <div className="flex flex-col gap-2">
        <h1 className="text-4xl font-bold tracking-tight">
          ModelGuard Dashboard
        </h1>
        <p className="text-muted-foreground">
          Monitor and manage your ML artifacts, models, and datasets
        </p>
      </div>

      {error && (
        <Alert variant="destructive" role="alert">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Connection Error</AlertTitle>
          <AlertDescription>
            {error.includes("Failed to fetch") || error.includes("HTTP")
              ? "Unable to connect to the backend API. Please ensure the backend server is running and accessible."
              : error}
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            <Activity
              className="h-4 w-4 text-muted-foreground"
              aria-hidden="true"
            />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {getHealthIcon(healthStatus)}
              <span
                className={`text-2xl font-bold ${getHealthColor(healthStatus)}`}
              >
                {healthStatus}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {healthStatus === "OK"
                ? "All systems operational"
                : "System issues detected"}
            </p>
            <Button
              className="mt-4 w-full"
              onClick={() => window.location.reload()}
              variant="outline"
              aria-label="Refresh system status"
            >
              Refresh
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total Artifacts
            </CardTitle>
            <Database
              className="h-4 w-4 text-muted-foreground"
              aria-hidden="true"
            />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{artifactCount}</div>
            <p className="text-xs text-muted-foreground mt-1">
              All artifact types
            </p>
            <Link
              to="/artifacts"
              search={{ type: undefined, q: undefined }}
              className="block mt-4"
            >
              <Button
                variant="outline"
                className="w-full"
                aria-label="View all artifacts"
              >
                View All
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Models</CardTitle>
            <TrendingUp
              className="h-4 w-4 text-muted-foreground"
              aria-hidden="true"
            />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{modelCount}</div>
            <p className="text-xs text-muted-foreground mt-1">
              ML models registered
            </p>
            <Link
              to="/artifacts"
              search={{ type: "model", q: undefined }}
              className="block mt-4"
            >
              <Button
                variant="outline"
                className="w-full"
                aria-label="View models"
              >
                View Models
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Datasets</CardTitle>
            <Database
              className="h-4 w-4 text-muted-foreground"
              aria-hidden="true"
            />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{datasetCount}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Training datasets
            </p>
            <Link
              to="/artifacts"
              search={{ type: "dataset", q: undefined }}
              className="block mt-4"
            >
              <Button
                variant="outline"
                className="w-full"
                aria-label="View datasets"
              >
                View Datasets
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Common tasks and navigation</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Link to="/upload" className="block">
              <Button className="w-full" aria-label="Upload new artifact">
                <Upload className="mr-2 h-4 w-4" aria-hidden="true" />
                Upload Artifact
              </Button>
            </Link>
            <Link
              to="/artifacts"
              search={{ type: undefined, q: undefined }}
              className="block"
            >
              <Button
                variant="outline"
                className="w-full"
                aria-label="Search artifacts"
              >
                <Search className="mr-2 h-4 w-4" aria-hidden="true" />
                Search Artifacts
              </Button>
            </Link>
            <Link
              to="/lineage"
              search={{ model_id: undefined }}
              className="block"
            >
              <Button
                variant="outline"
                className="w-full"
                aria-label="View model lineage"
              >
                <Network className="mr-2 h-4 w-4" aria-hidden="true" />
                View Lineage
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Artifact Types</CardTitle>
            <CardDescription>Breakdown by type</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <TrendingUp
                    className="h-4 w-4 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <span>Models</span>
                </div>
                <Badge variant="secondary">{modelCount}</Badge>
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Database
                    className="h-4 w-4 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <span>Datasets</span>
                </div>
                <Badge variant="secondary">{datasetCount}</Badge>
              </div>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Code
                    className="h-4 w-4 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <span>Code</span>
                </div>
                <Badge variant="secondary">{codeCount}</Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>System Information</CardTitle>
            <CardDescription>Current system status</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">Status:</span>
              <Badge
                variant={healthStatus === "OK" ? "default" : "destructive"}
                className={getHealthColor(healthStatus)}
              >
                {healthStatus}
              </Badge>
            </div>
            <Separator />
            <div className="flex justify-between">
              <span className="text-sm text-muted-foreground">
                Total Artifacts:
              </span>
              <span className="text-sm font-medium">{artifactCount}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
