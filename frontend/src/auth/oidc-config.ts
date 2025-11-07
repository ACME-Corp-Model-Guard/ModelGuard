export const cognitoAuthConfig = {
  authority: "https://cognito-idp.us-east-2.amazonaws.com/us-east-2_bR7vQ0H06",
  client_id: "1m6cd9ea5bqnfd1r1apmv5ngn6",
  redirect_uri: "https://d84l1y8p4kdic.cloudfront.net", // your deployed frontend
  response_type: "code",
  scope: "openid email phone",
}
