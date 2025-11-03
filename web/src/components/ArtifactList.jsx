import React from 'react';

export default function ArtifactList({ artifacts }) {
  if (!artifacts || artifacts.length === 0) return <p>No artifacts found.</p>;

  return (
    <table border="1" cellPadding="6" style={{ borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th>ID</th>
          <th>Name</th>
          <th>Type</th>
        </tr>
      </thead>
      <tbody>
        {artifacts.map((a) => (
          <tr key={a.id}>
            <td>{a.id}</td>
            <td>{a.name}</td>
            <td>{a.type}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
