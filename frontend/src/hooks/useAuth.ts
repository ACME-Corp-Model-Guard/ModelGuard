import { useAuth as useOidcAuth } from "react-oidc-context";
import { cognitoAuthConfig } from "@/auth/oidc-config";
import { cognitoConfig } from "@/auth/generated-config";

const getAppOrigin = () =>
  typeof window !== "undefined"
    ? window.location.origin
    : "http://localhost:3000";

export const useAuth = () => {
  const auth = useOidcAuth();

  const signOutRedirect = () => {
    const clientId = cognitoAuthConfig.client_id;
    const logoutUri = getAppOrigin(); // 🔒 ALWAYS app origin
    const cognitoDomain = cognitoConfig.domain;

    window.location.href =
      `${cognitoDomain}/logout` +
      `?client_id=${clientId}` +
      `&logout_uri=${encodeURIComponent(logoutUri)}`;
  };

  const getAuthHeader = () => {
    if (auth.user?.access_token) {
      return { "X-Authorization": `Bearer ${auth.user.access_token}` };
    }
    return {};
  };

  return { ...auth, signOutRedirect, getAuthHeader };
};

