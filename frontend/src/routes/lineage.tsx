import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Link } from "@tanstack/react-router";
import {
  Network,
  Loader2,
  AlertCircle,
  Search,
  ArrowRight,
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { getLineage } from "@/lib/api";

export const Route = createFileRoute("/lineage")({
  component: LineagePage,
  validateSearch: (search: Record<string, unknown>) => {
    return {
      model_id: (search.model_id as string) || undefined,
    };
  },
});

function LineagePage() {
  const auth = useAuth();
  const { model_id } = Route.useSearch();
  const [searchId, setSearchId] = useState<string>(model_id || "");
  const [lineageData, setLineageData] = useState<any>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (model_id && auth.isAuthenticated) {
      fetchLineage(model_id);
    }
  }, [model_id, auth.isAuthenticated]);

  const fetchLineage = async (id: string) => {
    try {
      setIsLoading(true);
      setError(null);
      const token = auth.user?.id_token;
      const data = await getLineage(id, token);
      setLineageData(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load lineage");
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchId.trim()) {
      fetchLineage(searchId.trim());
    }
  };

  if (!auth.isAuthenticated) {
    return (
      <div className="container mx-auto p-6">
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Authentication Required</AlertTitle>
          <AlertDescription>Please log in to view lineage.</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <main className="container mx-auto p-6 space-y-6" role="main">
      <div className="flex flex-col gap-2">
        <h1 className="text-4xl font-bold tracking-tight">Model Lineage</h1>
        <p className="text-muted-foreground">
          Visualize model relationships and dependencies
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Search Lineage</CardTitle>
          <CardDescription>
            Enter a model ID to view its lineage graph
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="flex gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search
                  className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground"
                  aria-hidden="true"
                />
                <Input
                  type="text"
                  placeholder="Enter model ID..."
                  value={searchId}
                  onChange={(e) => setSearchId(e.target.value)}
                  className="pl-10"
                  aria-label="Model ID for lineage search"
                />
              </div>
            </div>
            <Button
              type="submit"
              disabled={isLoading}
              aria-label="Search lineage"
            >
              {isLoading ? (
                <>
                  <Loader2
                    className="mr-2 h-4 w-4 animate-spin"
                    aria-hidden="true"
                  />
                  Loading...
                </>
              ) : (
                <>
                  <Network className="mr-2 h-4 w-4" aria-hidden="true" />
                  Search
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive" role="alert">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div
          className="flex items-center justify-center py-12"
          role="status"
          aria-live="polite"
        >
          <Loader2
            className="h-8 w-8 animate-spin text-primary"
            aria-hidden="true"
          />
          <span className="sr-only">Loading lineage...</span>
        </div>
      ) : lineageData ? (
        <Card>
          <CardHeader>
            <CardTitle>Lineage Graph</CardTitle>
            <CardDescription>Model relationships and hierarchy</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {lineageData.models && lineageData.models.length > 0 ? (
                <div className="space-y-6">
                  {lineageData.models.map((model: any, index: number) => (
                    <div
                      key={model.artifact_id || index}
                      className="border-l-4 border-primary pl-4"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-semibold">
                            {model.name || model.artifact_id}
                          </h3>
                          <p className="text-sm text-muted-foreground">
                            ID: {model.artifact_id}
                          </p>
                          {model.scores?.net_score && (
                            <p className="text-sm mt-1">
                              Net Score:{" "}
                              <span className="font-bold">
                                {(typeof model.scores.net_score === "number"
                                  ? model.scores.net_score
                                  : 0
                                ).toFixed(2)}
                              </span>
                            </p>
                          )}
                        </div>
                        <Link
                          to="/artifacts/$type/$id"
                          params={{ type: "model", id: model.artifact_id }}
                          search={{ type: undefined, q: undefined }}
                        >
                          <Button
                            variant="outline"
                            size="sm"
                            aria-label={`View details for ${model.name}`}
                          >
                            View Details
                            <ArrowRight
                              className="ml-2 h-4 w-4"
                              aria-hidden="true"
                            />
                          </Button>
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Network
                    className="h-12 w-12 mx-auto mb-4 opacity-50"
                    aria-hidden="true"
                  />
                  <p>No lineage data available for this model</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <Network
              className="h-12 w-12 mx-auto text-muted-foreground mb-4"
              aria-hidden="true"
            />
            <h3 className="text-lg font-semibold mb-2">No Lineage Selected</h3>
            <p className="text-muted-foreground mb-4">
              Enter a model ID above to view its lineage graph
            </p>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
