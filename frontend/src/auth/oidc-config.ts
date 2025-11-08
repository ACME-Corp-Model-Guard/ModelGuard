// Import with fallback - generated-config.ts should always exist (with placeholders or real values)
import { cognitoConfig } from './generated-config'

// Validate that config was properly generated
const validateConfig = () => {
  const hasPlaceholders = 
    cognitoConfig.userPoolId === "PLACEHOLDER" ||
    cognitoConfig.clientId === "PLACEHOLDER" ||
    cognitoConfig.domain === "PLACEHOLDER" ||
    cognitoConfig.authority === "PLACEHOLDER"

  if (hasPlaceholders) {
    const error = "🚨 COGNITO CONFIG ERROR: generated-config.ts still contains PLACEHOLDER values! This means the GitHub Actions workflow failed to populate the real Cognito configuration. Check the deployment logs."
    console.error(error)
    
    // Always show a prominent warning when placeholders are detected
    console.warn("⚠️  DEVELOPMENT MODE: Using placeholder Cognito config. Authentication will not work until real values are deployed.")
    
    // Also show an alert in the browser for maximum visibility
    if (typeof window !== 'undefined') {
      setTimeout(() => {
        alert("⚠️ COGNITO CONFIG WARNING: Using placeholder values. Check console for details.")
      }, 1000)
    }
  } else {
    console.log("✅ Cognito config successfully loaded with real values")
  }
}

// Run validation
validateConfig()

export const cognitoAuthConfig = {
  authority: cognitoConfig.authority,
  client_id: cognitoConfig.clientId,
  redirect_uri: window.location.origin,
  response_type: "code",
  scope: "openid",
}
