import { useAuth as useOidcAuth } from 'react-oidc-context'
import { cognitoAuthConfig } from '@/auth/oidc-config'

export const useAuth = () => {
  const auth = useOidcAuth()

  const signOutRedirect = () => {
    const clientId = cognitoAuthConfig.client_id
    const logoutUri = cognitoAuthConfig.redirect_uri
    const cognitoDomain = 'https://us-east-2br7vq0h06.auth.us-east-2.amazoncognito.com'
    window.location.href = `${cognitoDomain}/logout?client_id=${clientId}&logout_uri=${encodeURIComponent(logoutUri)}`
  }

  return { ...auth, signOutRedirect }
}
