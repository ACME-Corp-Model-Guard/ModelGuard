import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Link } from "@tanstack/react-router";
import {
  ArrowLeft,
  TrendingUp,
  Database,
  Code,
  Loader2,
  AlertCircle,
  ExternalLink,
  Network,
  BarChart3,
} from "lucide-react";
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import {
  getArtifact,
  getModelRate,
  type Artifact,
  type ModelRate,
} from "@/lib/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from "recharts";

export const Route = createFileRoute("/artifacts/$type/$id")({
  component: ArtifactDetailPage,
});

function ArtifactDetailPage() {
  const { type, id } = Route.useParams();
  const auth = useAuth();
  const [artifact, setArtifact] = useState<Artifact | null>(null);
  const [ratings, setRatings] = useState<ModelRate | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setIsLoading(true);
        setError(null);
        const token = auth.user?.id_token;

        const artifactData = await getArtifact(type, id, token);
        setArtifact(artifactData);

        // Fetch ratings if it's a model
        if (type === "model") {
          try {
            const rateData = await getModelRate(id, token);
            setRatings(rateData);
          } catch (e) {
            console.warn("Failed to fetch ratings:", e);
          }
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load artifact");
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    }

    if (auth.isAuthenticated) {
      fetchData();
    }
  }, [type, id, auth.isAuthenticated, auth.user?.id_token]);

  const getArtifactIcon = (type: string) => {
    switch (type) {
      case "model":
        return <TrendingUp className="h-6 w-6" aria-hidden="true" />;
      case "dataset":
        return <Database className="h-6 w-6" aria-hidden="true" />;
      case "code":
        return <Code className="h-6 w-6" aria-hidden="true" />;
      default:
        return <Database className="h-6 w-6" aria-hidden="true" />;
    }
  };

  const getArtifactTypeColor = (type: string) => {
    switch (type) {
      case "model":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
      case "dataset":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
      case "code":
        return "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200";
    }
  };

  const formatScore = (score: number | undefined): string => {
    if (score === undefined) return "N/A";
    return (score * 100).toFixed(1) + "%";
  };

  if (!auth.isAuthenticated) {
    return (
      <div className="container mx-auto p-6">
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Authentication Required</AlertTitle>
          <AlertDescription>
            Please log in to view artifact details.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="container mx-auto p-6">
        <div
          className="flex items-center justify-center py-12"
          role="status"
          aria-live="polite"
        >
          <Loader2
            className="h-8 w-8 animate-spin text-primary"
            aria-hidden="true"
          />
          <span className="sr-only">Loading artifact...</span>
        </div>
      </div>
    );
  }

  if (error || !artifact) {
    return (
      <div className="container mx-auto p-6">
        <Alert variant="destructive" role="alert">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error || "Artifact not found"}</AlertDescription>
        </Alert>
        <Link
          to="/artifacts"
          search={{ type: undefined, q: undefined }}
          className="mt-4 inline-block"
        >
          <Button variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" />
            Back to Artifacts
          </Button>
        </Link>
      </div>
    );
  }

  // Prepare chart data for metrics
  const metricsData = ratings
    ? [
        { name: "Net Score", value: ratings.net_score },
        { name: "Availability", value: ratings.availability },
        { name: "Bus Factor", value: ratings.bus_factor },
        { name: "Code Quality", value: ratings.code_quality },
        { name: "Dataset Quality", value: ratings.dataset_quality },
        { name: "License", value: ratings.license },
        { name: "Performance", value: ratings.performance_claims },
        { name: "Ramp Up", value: ratings.ramp_up },
        { name: "Tree Score", value: ratings.treescore },
      ]
    : [];

  const sizeData =
    ratings &&
    (ratings.size_pi ||
      ratings.size_nano ||
      ratings.size_pc ||
      ratings.size_server)
      ? [
          { device: "Pi (0.5GB)", score: ratings.size_pi || 0 },
          { device: "Nano (1GB)", score: ratings.size_nano || 0 },
          { device: "PC (16GB)", score: ratings.size_pc || 0 },
          { device: "Server (64GB)", score: ratings.size_server || 0 },
        ]
      : [];

  return (
    <main className="container mx-auto p-6 space-y-6" role="main">
      <div className="flex items-center gap-4">
        <Link to="/artifacts" search={{ type: undefined, q: undefined }}>
          <Button variant="ghost" size="icon" aria-label="Back to artifacts">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            {getArtifactIcon(artifact.artifact_type)}
            <h1 className="text-4xl font-bold tracking-tight">
              {artifact.name}
            </h1>
            <Badge className={getArtifactTypeColor(artifact.artifact_type)}>
              {artifact.artifact_type}
            </Badge>
          </div>
          <p className="text-muted-foreground mt-1">
            Artifact ID: {artifact.artifact_id}
          </p>
        </div>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          {type === "model" && (
            <TabsTrigger value="metrics">Metrics</TabsTrigger>
          )}
          <TabsTrigger value="metadata">Metadata</TabsTrigger>
          {artifact.parent_model_id ||
          (artifact.child_model_ids && artifact.child_model_ids.length > 0) ? (
            <TabsTrigger value="lineage">Lineage</TabsTrigger>
          ) : null}
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Basic Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <span className="text-sm text-muted-foreground">Name:</span>
                  <p className="font-medium">{artifact.name}</p>
                </div>
                <Separator />
                <div>
                  <span className="text-sm text-muted-foreground">Type:</span>
                  <p className="font-medium capitalize">
                    {artifact.artifact_type}
                  </p>
                </div>
                {artifact.version && (
                  <>
                    <Separator />
                    <div>
                      <span className="text-sm text-muted-foreground">
                        Version:
                      </span>
                      <p className="font-medium">{artifact.version}</p>
                    </div>
                  </>
                )}
                {artifact.license && (
                  <>
                    <Separator />
                    <div>
                      <span className="text-sm text-muted-foreground">
                        License:
                      </span>
                      <p className="font-medium">{artifact.license}</p>
                    </div>
                  </>
                )}
                {artifact.size && (
                  <>
                    <Separator />
                    <div>
                      <span className="text-sm text-muted-foreground">
                        Size:
                      </span>
                      <p className="font-medium">
                        {(artifact.size / (1024 * 1024)).toFixed(2)} MB
                      </p>
                    </div>
                  </>
                )}
                {artifact.source_url && (
                  <>
                    <Separator />
                    <div>
                      <span className="text-sm text-muted-foreground">
                        Source URL:
                      </span>
                      <a
                        href={artifact.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-primary hover:underline"
                        aria-label={`Open source URL in new tab`}
                      >
                        {artifact.source_url}
                        <ExternalLink className="h-4 w-4" aria-hidden="true" />
                      </a>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            {type === "model" && ratings && (
              <Card>
                <CardHeader>
                  <CardTitle>Overall Score</CardTitle>
                  <CardDescription>
                    Net Score represents overall quality
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between mb-2">
                        <span className="text-sm font-medium">Net Score</span>
                        <span className="text-sm font-bold">
                          {formatScore(ratings.net_score)}
                        </span>
                      </div>
                      <Progress
                        value={(ratings.net_score || 0) * 100}
                        className="h-3"
                        aria-label={`Net score: ${formatScore(ratings.net_score)}`}
                      />
                    </div>
                    <Separator />
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <span className="text-xs text-muted-foreground">
                          Availability
                        </span>
                        <p className="text-lg font-semibold">
                          {formatScore(ratings.availability)}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground">
                          Code Quality
                        </span>
                        <p className="text-lg font-semibold">
                          {formatScore(ratings.code_quality)}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground">
                          License
                        </span>
                        <p className="text-lg font-semibold">
                          {formatScore(ratings.license)}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground">
                          Performance
                        </span>
                        <p className="text-lg font-semibold">
                          {formatScore(ratings.performance_claims)}
                        </p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        {type === "model" && (
          <TabsContent value="metrics" className="space-y-4">
            {ratings ? (
              <>
                <Card>
                  <CardHeader>
                    <CardTitle>Metric Scores</CardTitle>
                    <CardDescription>
                      Detailed breakdown of all metrics
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {metricsData.map((metric) => (
                        <div key={metric.name}>
                          <div className="flex justify-between mb-2">
                            <span className="text-sm font-medium">
                              {metric.name}
                            </span>
                            <span className="text-sm font-bold">
                              {formatScore(metric.value)}
                            </span>
                          </div>
                          <Progress
                            value={(metric.value || 0) * 100}
                            className="h-2"
                            aria-label={`${metric.name}: ${formatScore(metric.value)}`}
                          />
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                {sizeData.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle>Size Compatibility</CardTitle>
                      <CardDescription>
                        Model size scores for different devices
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={sizeData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="device" />
                          <YAxis domain={[0, 1]} />
                          <Tooltip
                            formatter={(value: number) => formatScore(value)}
                          />
                          <Bar dataKey="score" fill="hsl(var(--primary))" />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                )}

                <Card>
                  <CardHeader>
                    <CardTitle>Metrics Radar Chart</CardTitle>
                    <CardDescription>
                      Visual comparison of all metrics
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={400}>
                      <RadarChart data={metricsData}>
                        <PolarGrid />
                        <PolarAngleAxis dataKey="name" />
                        <PolarRadiusAxis domain={[0, 1]} />
                        <Radar
                          name="Score"
                          dataKey="value"
                          stroke="hsl(var(--primary))"
                          fill="hsl(var(--primary))"
                          fillOpacity={0.6}
                        />
                        <Tooltip
                          formatter={(value: number) => formatScore(value)}
                        />
                      </RadarChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              </>
            ) : (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>No Metrics Available</AlertTitle>
                <AlertDescription>
                  Metrics have not been calculated for this model yet.
                </AlertDescription>
              </Alert>
            )}
          </TabsContent>
        )}

        <TabsContent value="metadata" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Metadata</CardTitle>
              <CardDescription>Raw metadata for this artifact</CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="bg-muted p-4 rounded-lg overflow-auto text-sm">
                {JSON.stringify(artifact.metadata || {}, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>

        {(artifact.parent_model_id ||
          (artifact.child_model_ids &&
            artifact.child_model_ids.length > 0)) && (
          <TabsContent value="lineage" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Model Lineage</CardTitle>
                <CardDescription>
                  Parent and child model relationships
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {artifact.parent_model_id && (
                  <div>
                    <span className="text-sm text-muted-foreground">
                      Parent Model:
                    </span>
                    <Link
                      to="/artifacts/$type/$id"
                      params={{ type: "model", id: artifact.parent_model_id }}
                      search={{ type: undefined, q: undefined }}
                      className="block mt-1"
                    >
                      <Button
                        variant="outline"
                        className="w-full justify-start"
                      >
                        <Network className="mr-2 h-4 w-4" aria-hidden="true" />
                        {artifact.parent_model_id}
                      </Button>
                    </Link>
                  </div>
                )}
                {artifact.child_model_ids &&
                  artifact.child_model_ids.length > 0 && (
                    <div>
                      <span className="text-sm text-muted-foreground">
                        Child Models:
                      </span>
                      <div className="mt-2 space-y-2">
                        {artifact.child_model_ids.map((childId) => (
                          <Link
                            key={childId}
                            to="/artifacts/$type/$id"
                            params={{ type: "model", id: childId }}
                            search={{ type: undefined, q: undefined }}
                            className="block"
                          >
                            <Button
                              variant="outline"
                              className="w-full justify-start"
                            >
                              <Network
                                className="mr-2 h-4 w-4"
                                aria-hidden="true"
                              />
                              {childId}
                            </Button>
                          </Link>
                        ))}
                      </div>
                    </div>
                  )}
                <Link to="/lineage" search={{ model_id: artifact.artifact_id }}>
                  <Button
                    className="w-full mt-4"
                    aria-label="View full lineage graph"
                  >
                    <BarChart3 className="mr-2 h-4 w-4" aria-hidden="true" />
                    View Full Lineage Graph
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </main>
  );
}
