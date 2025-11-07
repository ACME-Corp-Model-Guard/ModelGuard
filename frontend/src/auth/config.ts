export const cognitoAuthConfig = {
  authority: "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_pULwY76Ur", // Replace with your pool ID region
  client_id: "49ijlghtgd4umt4v7ff92pjta7", // Replace with your app client ID
  redirect_uri: "https://d84l1y8p4kdic.cloudfront.net", // Replace with your CloudFront domain
  response_type: "code", // Required for Authorization Code flow
  scope: "openid email phone profile", // Add profile for user attributes
};
