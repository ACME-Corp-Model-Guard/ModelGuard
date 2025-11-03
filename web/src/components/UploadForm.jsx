import React, { useState } from 'react';
import { createArtifact } from '../api/modelApi';

export default function UploadForm({ token }) {
  const [url, setUrl] = useState('');
  const [artifactType, setArtifactType] = useState('model');
  const [status, setStatus] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus('Uploading...');
    try {
      await createArtifact(artifactType, { url }, token);
      setStatus('Upload successful!');
    } catch (err) {
      console.error(err);
      setStatus('Upload failed.');
    }
  };

  return (
    <form onSubmit={handleSubmit} style={{ marginBottom: '20px' }}>
      <label>
        URL: <input type="text" value={url} onChange={(e) => setUrl(e.target.value)} required />
      </label>
      <label style={{ marginLeft: '10px' }}>
        Type:
        <select value={artifactType} onChange={(e) => setArtifactType(e.target.value)}>
          <option value="model">model</option>
          <option value="dataset">dataset</option>
          <option value="code">code</option>
        </select>
      </label>
      <button type="submit" style={{ marginLeft: '10px' }}>Upload</button>
      <div>{status}</div>
    </form>
  );
}
