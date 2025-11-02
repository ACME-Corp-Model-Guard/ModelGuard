import { API_BASE } from '../config';

/**
 * Headers helper
 */
const authHeader = (token) => ({
  'X-Authorization': token,
  'Content-Type': 'application/json',
});

/** --------------------
 * Health Endpoints
 * -------------------- */
export async function getHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('Health check failed');
  return res.json();
}

export async function getComponentHealth(windowMinutes = 60, includeTimeline = false) {
  const res = await fetch(
    `${API_BASE}/health/components?windowMinutes=${windowMinutes}&includeTimeline=${includeTimeline}`
  );
  if (!res.ok) throw new Error('Component health failed');
  return res.json();
}

/** --------------------
 * Artifact Endpoints
 * -------------------- */
export async function getArtifacts(artifactQueryArray, offset = 0, token) {
  const res = await fetch(`${API_BASE}/artifacts?offset=${offset}`, {
    method: 'POST',
    headers: authHeader(token),
    body: JSON.stringify(artifactQueryArray),
  });
  if (!res.ok) throw new Error('Artifacts list failed');
  return res.json();
}

export async function getArtifactById(type, id, token) {
  const res = await fetch(`${API_BASE}/artifacts/${type}/${id}`, {
    headers: authHeader(token),
  });
  if (!res.ok) throw new Error(`Artifact ${id} fetch failed`);
  return res.json();
}

export async function createArtifact(type, artifactData, token) {
  const res = await fetch(`${API_BASE}/artifact/${type}`, {
    method: 'POST',
    headers: authHeader(token),
    body: JSON.stringify(artifactData),
  });
  if (!res.ok) throw new Error('Artifact creation failed');
  return res.json();
}

export async function updateArtifact(type, id, artifactPayload, token) {
  const res = await fetch(`${API_BASE}/artifact/${type}/${id}`, {
    method: 'PUT',
    headers: authHeader(token),
    body: JSON.stringify(artifactPayload),
  });
  if (!res.ok) throw new Error('Artifact update failed');
  return res.json();
}

export async function deleteArtifact(type, id, token) {
  const res = await fetch(`${API_BASE}/artifact/${type}/${id}`, {
    method: 'DELETE',
    headers: authHeader(token),
  });
  if (!res.ok) throw new Error('Artifact deletion failed');
  return res.json();
}

export async function getArtifactRate(id, token) {
  const res = await fetch(`${API_BASE}/artifact/model/${id}/rate`, {
    headers: authHeader(token),
  });
  if (!res.ok) throw new Error('Model rate fetch failed');
  return res.json();
}

export async function getArtifactCost(type, id, token, dependency = false) {
  const url = `${API_BASE}/artifact/${type}/${id}/cost?dependency=${dependency}`;
  const res = await fetch(url, { headers: authHeader(token) });
  if (!res.ok) throw new Error('Artifact cost fetch failed');
  return res.json();
}

export async function licenseCheck(id, githubUrl, token) {
  const res = await fetch(`${API_BASE}/artifact/model/${id}/license-check`, {
    method: 'POST',
    headers: authHeader(token),
    body: JSON.stringify({ github_url: githubUrl }),
  });
  if (!res.ok) throw new Error('License check failed');
  return res.json();
}

export async function searchByName(name, token) {
  const res = await fetch(`${API_BASE}/artifact/byName/${name}`, {
    headers: authHeader(token),
  });
  if (!res.ok) throw new Error('Search by name failed');
  return res.json();
}

export async function searchByRegEx(regexPattern, token) {
  const res = await fetch(`${API_BASE}/artifact/byRegEx`, {
    method: 'POST',
    headers: authHeader(token),
    body: JSON.stringify({ regex: regexPattern }),
  });
  if (!res.ok) throw new Error('Search by regex failed');
  return res.json();
}

/** --------------------
 * Authentication
 * -------------------- */
export async function authenticate(user, password) {
  const payload = { user, secret: { password } };
  const res = await fetch(`${API_BASE}/authenticate`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Authentication failed');
  const token = await res.json();
  return token; // Use this as `X-Authorization` in subsequent requests
}

/** --------------------
 * Reset Registry
 * -------------------- */
export async function resetRegistry(token) {
  const res = await fetch(`${API_BASE}/reset`, {
    method: 'DELETE',
    headers: authHeader(token),
  });
  if (!res.ok) throw new Error('Registry reset failed');
  return res.json();
}
