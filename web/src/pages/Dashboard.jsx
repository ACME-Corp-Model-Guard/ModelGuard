import React, { useEffect, useState } from 'react';
import { authenticate, getArtifacts } from '../api/modelApi';
import ArtifactList from '../components/ArtifactList';
import UploadForm from '../components/UploadForm';

export default function Dashboard() {
  const [token, setToken] = useState('');
  const [artifacts, setArtifacts] = useState([]);
  const [query, setQuery] = useState('');

  const loginAndLoad = async () => {
    // Use default admin user for testing
    const t = await authenticate(
      { name: 'ece30861defaultadminuser', is_admin: true },
      'correcthorsebatterystaple123(!__+@**(A\'"`;DROP TABLE artifacts;'
    );
    setToken(t);

    const allArtifacts = await getArtifacts([{ name: '*' }], 0, t);
    setArtifacts(allArtifacts);
  };

  useEffect(() => {
    loginAndLoad();
  }, []);

  const handleSearch = async () => {
    if (!query) return;
    try {
      const results = await getArtifacts([{ name: query }], 0, token);
      setArtifacts(results);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <h1>Model-Guard Dashboard</h1>

      <UploadForm token={token} />

      <div style={{ marginBottom: '10px' }}>
        <input
          type="text"
          placeholder="Search by artifact name"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button onClick={handleSearch} style={{ marginLeft: '5px' }}>Search</button>
      </div>

      <ArtifactList artifacts={artifacts} />
    </div>
  );
}
