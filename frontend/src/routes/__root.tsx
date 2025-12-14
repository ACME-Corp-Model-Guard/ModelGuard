import { HeadContent, Scripts, createRootRoute } from "@tanstack/react-router";
import { TanStackRouterDevtoolsPanel } from "@tanstack/react-router-devtools";
import { TanStackDevtools } from "@tanstack/react-devtools";

import Header from "../components/Header";
import { AuthProvider } from "react-oidc-context";
import { cognitoAuthConfig } from "@/auth/oidc-config";

import appCss from "../styles.css?url";

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "ModelGuard - ML Artifact Management" },
      {
        name: "description",
        content: "Manage and monitor ML models, datasets, and code artifacts",
      },
    ],
    links: [{ rel: "stylesheet", href: appCss }],
  }),
  shellComponent: RootDocument,
});

function RootDocument({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <HeadContent />
      </head>
      <body>
        {/* Skip to main content link for accessibility */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md"
        >
          Skip to main content
        </a>

        {/* Wrap the app in Cognito AuthProvider */}
        <AuthProvider {...cognitoAuthConfig}>
          <Header />
          <div id="main-content" tabIndex={-1}>
            {children}
          </div>
        </AuthProvider>

        {/* Optional Devtools */}
        {import.meta.env.DEV && (
          <>
            <TanStackRouterDevtoolsPanel />
            <TanStackDevtools />
          </>
        )}
        <Scripts />
      </body>
    </html>
  );
}
