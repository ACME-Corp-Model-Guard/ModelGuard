import { useAuth } from "react-oidc-context";

function App() {
  const auth = useAuth();

  const logout = () => {
    const clientId = "49ijlghtgd4umt4v7ff92pjta7";
    const logoutUri = "https://d84l1y8p4kdic.cloudfront.net";
    const cognitoDomain = "https://us-east-1pulwy76ur.auth.us-east-1.amazoncognito.com";

    window.location.href = `${cognitoDomain}/logout?client_id=${clientId}&logout_uri=${encodeURIComponent(logoutUri)}`;
  };

  if (auth.isLoading) {
    return <div className="p-4 text-gray-600">Loading authentication...</div>;
  }

  if (auth.error) {
    return <div className="text-red-500">Error: {auth.error.message}</div>;
  }

  if (auth.isAuthenticated) {
    return (
      <div className="p-6 text-gray-900">
        <h1 className="text-2xl mb-2">Hello, {auth.user?.profile.email}</h1>
        <p>ID Token: {auth.user?.id_token}</p>
        <p>Access Token: {auth.user?.access_token}</p>
        <button
          onClick={() => logout()}
          className="mt-4 px-4 py-2 bg-red-500 text-white rounded"
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className="p-6">
      <button
        onClick={() => auth.signinRedirect()}
        className="px-4 py-2 bg-blue-500 text-white rounded"
      >
        Sign in
      </button>
    </div>
  );
}

export default App;
