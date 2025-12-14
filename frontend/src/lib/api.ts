/**
 * API utility functions for ModelGuard
 * Handles authenticated requests to the backend API
 */

export interface Artifact {
  artifact_id: string;
  artifact_type: "model" | "dataset" | "code";
  name: string;
  source_url: string;
  version?: string;
  size?: number;
  license?: string;
  metadata?: Record<string, any>;
  scores?: Record<string, number | Record<string, number>>;
  scores_latency?: Record<string, number>;
  code_artifact_id?: string;
  dataset_artifact_id?: string;
  parent_model_id?: string;
  child_model_ids?: string[];
}

export interface ModelRate {
  net_score: number;
  availability: number;
  bus_factor: number;
  code_quality: number;
  dataset_quality: number;
  license: number;
  performance_claims: number;
  ramp_up: number;
  size_pi?: number;
  size_nano?: number;
  size_pc?: number;
  size_server?: number;
  treescore: number;
}

// API base URL - defaults to empty string for relative URLs (proxy through Vite)
// Set VITE_API_URL environment variable to point to your backend API
const API_BASE_URL = import.meta.env.VITE_API_URL || "";

/**
 * Get authorization headers for API requests
 */
function getAuthHeaders(token?: string): HeadersInit {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["X-Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

/**
 * Handle API errors gracefully
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.message || errorData.error || errorMessage;
    } catch {
      // If response isn't JSON, use status text
    }
    throw new Error(errorMessage);
  }
  return response.json();
}

/**
 * Fetch health status
 */
export async function fetchHealth(token?: string): Promise<{ status: string }> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    headers: getAuthHeaders(token),
  });
  return handleResponse<{ status: string }>(response);
}

/**
 * List artifacts with optional filters
 */
export async function listArtifacts(
  filters: Array<{ name?: string; artifact_type?: string }> = [{ name: "*" }],
  token?: string,
): Promise<Artifact[]> {
  const response = await fetch(`${API_BASE_URL}/artifacts`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify(filters),
  });
  return handleResponse<Artifact[]>(response);
}

/**
 * Get artifact by type and ID
 */
export async function getArtifact(
  artifactType: string,
  id: string,
  token?: string,
): Promise<Artifact> {
  const response = await fetch(
    `${API_BASE_URL}/artifacts/${artifactType}/${id}`,
    {
      headers: getAuthHeaders(token),
    },
  );
  return handleResponse<Artifact>(response);
}

/**
 * Get model ratings/scores
 */
export async function getModelRate(
  modelId: string,
  token?: string,
): Promise<ModelRate> {
  const response = await fetch(
    `${API_BASE_URL}/artifact/model/${modelId}/rate`,
    {
      headers: getAuthHeaders(token),
    },
  );
  return handleResponse<ModelRate>(response);
}

/**
 * Search artifacts by name
 */
export async function searchByName(
  name: string,
  token?: string,
): Promise<Artifact[]> {
  const response = await fetch(
    `${API_BASE_URL}/artifact/byName/${encodeURIComponent(name)}`,
    {
      headers: getAuthHeaders(token),
    },
  );
  return handleResponse<Artifact[]>(response);
}

/**
 * Search artifacts by regex
 */
export async function searchByRegex(
  pattern: string,
  token?: string,
): Promise<Artifact[]> {
  const response = await fetch(`${API_BASE_URL}/artifact/byRegEx`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify({ pattern }),
  });
  return handleResponse<Artifact[]>(response);
}

/**
 * Get lineage for a model
 */
export async function getLineage(
  modelId: string,
  token?: string,
): Promise<any> {
  const response = await fetch(
    `${API_BASE_URL}/lineage?model_id=${encodeURIComponent(modelId)}`,
    {
      headers: getAuthHeaders(token),
    },
  );
  return handleResponse<any>(response);
}

/**
 * Upload artifact
 */
export async function uploadArtifact(
  artifactType: "model" | "dataset" | "code",
  data: {
    name: string;
    source_url: string;
    version?: string;
  },
  token?: string,
): Promise<Artifact> {
  const response = await fetch(`${API_BASE_URL}/artifact/${artifactType}`, {
    method: "POST",
    headers: getAuthHeaders(token),
    body: JSON.stringify(data),
  });
  return handleResponse<Artifact>(response);
}
