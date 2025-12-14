import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Link } from "@tanstack/react-router";
import {
  Search,
  Filter,
  Database,
  Code,
  TrendingUp,
  Loader2,
  AlertCircle,
  ExternalLink,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  listArtifacts,
  searchByName,
  searchByRegex,
  type Artifact,
} from "@/lib/api";

export const Route = createFileRoute("/artifacts")({
  component: ArtifactsPage,
  validateSearch: (search: Record<string, unknown>) => {
    return {
      type: (search.type as string) || undefined,
      q: (search.q as string) || undefined,
    };
  },
});

function ArtifactsPage() {
  const auth = useAuth();
  const { type, q } = Route.useSearch();

  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [filteredArtifacts, setFilteredArtifacts] = useState<Artifact[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>(q || "");
  const [filterType, setFilterType] = useState<string>(type || "all");
  const [searchMode, setSearchMode] = useState<"name" | "regex">("name");

  useEffect(() => {
    async function fetchArtifacts() {
      try {
        setIsLoading(true);
        setError(null);
        const token = auth.user?.id_token;

        if (searchQuery.trim()) {
          let results: Artifact[];
          if (searchMode === "regex") {
            results = await searchByRegex(searchQuery, token);
          } else {
            results = await searchByName(searchQuery, token);
          }
          setArtifacts(results);
        } else {
          const results = await listArtifacts([{ name: "*" }], token);
          setArtifacts(results);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load artifacts");
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    }

    if (auth.isAuthenticated) {
      fetchArtifacts();
    }
  }, [auth.isAuthenticated, auth.user?.id_token, searchQuery, searchMode]);

  useEffect(() => {
    let filtered = artifacts;

    if (filterType !== "all") {
      filtered = filtered.filter((a) => a.artifact_type === filterType);
    }

    setFilteredArtifacts(filtered);
  }, [artifacts, filterType]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    // Search is handled by useEffect
  };

  const getArtifactIcon = (type: string) => {
    switch (type) {
      case "model":
        return <TrendingUp className="h-5 w-5" aria-hidden="true" />;
      case "dataset":
        return <Database className="h-5 w-5" aria-hidden="true" />;
      case "code":
        return <Code className="h-5 w-5" aria-hidden="true" />;
      default:
        return <Database className="h-5 w-5" aria-hidden="true" />;
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

  if (!auth.isAuthenticated) {
    return (
      <div className="container mx-auto p-6">
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Authentication Required</AlertTitle>
          <AlertDescription>Please log in to view artifacts.</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <main className="container mx-auto p-6 space-y-6" role="main">
      <div className="flex flex-col gap-2">
        <h1 className="text-4xl font-bold tracking-tight">Artifacts</h1>
        <p className="text-muted-foreground">
          Browse and search through all registered artifacts
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Search & Filter</CardTitle>
          <CardDescription>
            Find artifacts by name or use regex patterns
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="flex gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search
                    className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <Input
                    type="text"
                    placeholder={
                      searchMode === "regex"
                        ? "Enter regex pattern..."
                        : "Search by name..."
                    }
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                    aria-label="Search artifacts"
                  />
                </div>
              </div>
              <Select
                value={searchMode}
                onValueChange={(v) => setSearchMode(v as "name" | "regex")}
              >
                <SelectTrigger className="w-[140px]" aria-label="Search mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="name">By Name</SelectItem>
                  <SelectItem value="regex">By Regex</SelectItem>
                </SelectContent>
              </Select>
              <Button type="submit" aria-label="Search">
                <Search className="mr-2 h-4 w-4" aria-hidden="true" />
                Search
              </Button>
            </div>

            <div className="flex items-center gap-2">
              <Filter
                className="h-4 w-4 text-muted-foreground"
                aria-hidden="true"
              />
              <span className="text-sm text-muted-foreground">
                Filter by type:
              </span>
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger
                  className="w-[140px]"
                  aria-label="Filter by artifact type"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Types</SelectItem>
                  <SelectItem value="model">Models</SelectItem>
                  <SelectItem value="dataset">Datasets</SelectItem>
                  <SelectItem value="code">Code</SelectItem>
                </SelectContent>
              </Select>
            </div>
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
          <span className="sr-only">Loading artifacts...</span>
        </div>
      ) : filteredArtifacts.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Database
              className="h-12 w-12 mx-auto text-muted-foreground mb-4"
              aria-hidden="true"
            />
            <h3 className="text-lg font-semibold mb-2">No artifacts found</h3>
            <p className="text-muted-foreground mb-4">
              {searchQuery
                ? "Try adjusting your search query"
                : "No artifacts are registered yet"}
            </p>
            {!searchQuery && (
              <Link to="/upload">
                <Button aria-label="Upload first artifact">
                  Upload Artifact
                </Button>
              </Link>
            )}
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Showing {filteredArtifacts.length} of {artifacts.length} artifacts
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredArtifacts.map((artifact) => (
              <Card
                key={artifact.artifact_id}
                className="hover:shadow-lg transition-shadow"
              >
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      {getArtifactIcon(artifact.artifact_type)}
                      <div>
                        <CardTitle className="text-lg">
                          {artifact.name}
                        </CardTitle>
                        <CardDescription className="mt-1">
                          {artifact.artifact_id}
                        </CardDescription>
                      </div>
                    </div>
                    <Badge
                      className={getArtifactTypeColor(artifact.artifact_type)}
                    >
                      {artifact.artifact_type}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {artifact.version && (
                    <div>
                      <span className="text-sm text-muted-foreground">
                        Version:{" "}
                      </span>
                      <span className="text-sm font-medium">
                        {artifact.version}
                      </span>
                    </div>
                  )}

                  {artifact.license && (
                    <div>
                      <span className="text-sm text-muted-foreground">
                        License:{" "}
                      </span>
                      <span className="text-sm font-medium">
                        {artifact.license}
                      </span>
                    </div>
                  )}

                  {artifact.size && (
                    <div>
                      <span className="text-sm text-muted-foreground">
                        Size:{" "}
                      </span>
                      <span className="text-sm font-medium">
                        {(artifact.size / (1024 * 1024)).toFixed(2)} MB
                      </span>
                    </div>
                  )}

                  {artifact.scores?.net_score && (
                    <div>
                      <span className="text-sm text-muted-foreground">
                        Net Score:{" "}
                      </span>
                      <span className="text-sm font-bold">
                        {(typeof artifact.scores.net_score === "number"
                          ? artifact.scores.net_score
                          : 0
                        ).toFixed(2)}
                      </span>
                    </div>
                  )}

                  <div className="flex gap-2 pt-2">
                    <Link
                      to="/artifacts/$type/$id"
                      params={{
                        type: artifact.artifact_type,
                        id: artifact.artifact_id,
                      }}
                      search={{ type: undefined, q: undefined }}
                      className="flex-1"
                    >
                      <Button
                        variant="default"
                        className="w-full"
                        aria-label={`View details for ${artifact.name}`}
                      >
                        View Details
                      </Button>
                    </Link>
                    {artifact.source_url && (
                      <a
                        href={artifact.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`Open source URL for ${artifact.name} in new tab`}
                      >
                        <Button variant="outline" size="icon">
                          <ExternalLink
                            className="h-4 w-4"
                            aria-hidden="true"
                          />
                        </Button>
                      </a>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </main>
  );
}
