import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { Upload, Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { uploadArtifact } from "@/lib/api";

export const Route = createFileRoute("/upload")({ component: UploadPage });

function UploadPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const [artifactType, setArtifactType] = useState<
    "model" | "dataset" | "code"
  >("model");
  const [name, setName] = useState<string>("");
  const [sourceUrl, setSourceUrl] = useState<string>("");
  const [version, setVersion] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!name.trim() || !sourceUrl.trim()) {
      setError("Name and Source URL are required");
      return;
    }

    // Validate URL format
    try {
      new URL(sourceUrl);
    } catch {
      setError("Invalid URL format");
      return;
    }

    setIsLoading(true);

    try {
      const token = auth.user?.id_token;
      const artifact = await uploadArtifact(
        artifactType,
        {
          name: name.trim(),
          source_url: sourceUrl.trim(),
          version: version.trim() || undefined,
        },
        token,
      );

      setSuccess(`Artifact "${artifact.name}" uploaded successfully!`);

      // Redirect to artifact detail page after 2 seconds
      setTimeout(() => {
        navigate({
          to: "/artifacts/$type/$id",
          params: { type: artifact.artifact_type, id: artifact.artifact_id },
          search: { type: undefined, q: undefined },
        });
      }, 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to upload artifact");
    } finally {
      setIsLoading(false);
    }
  };

  if (!auth.isAuthenticated) {
    return (
      <div className="container mx-auto p-6">
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Authentication Required</AlertTitle>
          <AlertDescription>
            Please log in to upload artifacts.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <main className="container mx-auto p-6 max-w-2xl" role="main">
      <div className="flex flex-col gap-2 mb-6">
        <h1 className="text-4xl font-bold tracking-tight">Upload Artifact</h1>
        <p className="text-muted-foreground">
          Register a new model, dataset, or code artifact
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Artifact Information</CardTitle>
          <CardDescription>
            Provide details about the artifact you want to upload
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="artifact-type">Artifact Type *</Label>
              <Select
                value={artifactType}
                onValueChange={(v) =>
                  setArtifactType(v as "model" | "dataset" | "code")
                }
              >
                <SelectTrigger
                  id="artifact-type"
                  aria-label="Select artifact type"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="model">Model</SelectItem>
                  <SelectItem value="dataset">Dataset</SelectItem>
                  <SelectItem value="code">Code</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Select the type of artifact you're uploading
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="name">Name *</Label>
              <Input
                id="name"
                type="text"
                placeholder="e.g., bert-base-uncased"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                aria-required="true"
                aria-describedby="name-description"
              />
              <p
                id="name-description"
                className="text-xs text-muted-foreground"
              >
                A unique name for this artifact
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="source-url">Source URL *</Label>
              <Input
                id="source-url"
                type="url"
                placeholder="https://huggingface.co/model-name or https://github.com/owner/repo"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                required
                aria-required="true"
                aria-describedby="url-description"
              />
              <p id="url-description" className="text-xs text-muted-foreground">
                URL to the artifact source (HuggingFace for models/datasets,
                GitHub for code)
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="version">Version</Label>
              <Input
                id="version"
                type="text"
                placeholder="e.g., 1.0.0"
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                aria-describedby="version-description"
              />
              <p
                id="version-description"
                className="text-xs text-muted-foreground"
              >
                Optional version identifier
              </p>
            </div>

            {error && (
              <Alert variant="destructive" role="alert">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert role="alert">
                <CheckCircle2 className="h-4 w-4" />
                <AlertTitle>Success</AlertTitle>
                <AlertDescription>{success}</AlertDescription>
              </Alert>
            )}

            <div className="flex gap-4">
              <Button
                type="submit"
                disabled={isLoading}
                className="flex-1"
                aria-label="Upload artifact"
              >
                {isLoading ? (
                  <>
                    <Loader2
                      className="mr-2 h-4 w-4 animate-spin"
                      aria-hidden="true"
                    />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="mr-2 h-4 w-4" aria-hidden="true" />
                    Upload Artifact
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Supported Sources</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc list-inside space-y-2 text-sm text-muted-foreground">
            <li>
              <strong>Models & Datasets:</strong> HuggingFace Hub URLs (e.g.,{" "}
              <code className="bg-muted px-1 rounded">
                https://huggingface.co/model-name
              </code>
              )
            </li>
            <li>
              <strong>Code:</strong> GitHub repository URLs (e.g.,{" "}
              <code className="bg-muted px-1 rounded">
                https://github.com/owner/repo
              </code>
              )
            </li>
          </ul>
        </CardContent>
      </Card>
    </main>
  );
}
