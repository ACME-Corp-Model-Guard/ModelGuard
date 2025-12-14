import { Link, useRouterState } from "@tanstack/react-router";
import { useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import {
  Home,
  Menu,
  Network,
  Database,
  Upload,
  X,
  LogOut,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export default function Header() {
  const [isOpen, setIsOpen] = useState(false);
  const auth = useAuth();
  const router = useRouterState();
  const currentPath = router.location.pathname;

  const handleLogout = () => {
    auth.signoutRedirect();
  };

  const navItems = [
    { to: "/", label: "Dashboard", icon: Home },
    { to: "/artifacts", label: "Artifacts", icon: Database },
    { to: "/upload", label: "Upload", icon: Upload },
    { to: "/lineage", label: "Lineage", icon: Network },
  ];

  const isActive = (path: string) => {
    if (path === "/") {
      return currentPath === "/";
    }
    return currentPath.startsWith(path);
  };

  return (
    <>
      <header
        className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60"
        role="banner"
      >
        <div className="container flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsOpen(true)}
              className="p-2 hover:bg-accent rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              aria-label="Open navigation menu"
              aria-expanded={isOpen}
              aria-controls="navigation-menu"
            >
              <Menu size={24} aria-hidden="true" />
            </button>
            <Link
              to="/"
              className="flex items-center gap-2 font-semibold text-xl hover:opacity-80 transition-opacity focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 rounded"
              aria-label="ModelGuard Home"
            >
              <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                ModelGuard
              </span>
            </Link>
          </div>

          {auth.isAuthenticated && (
            <div className="flex items-center gap-4">
              <div className="hidden md:flex items-center gap-2 text-sm text-muted-foreground">
                <User className="h-4 w-4" aria-hidden="true" />
                <span>
                  {auth.user?.profile?.name ||
                    auth.user?.profile?.email ||
                    "User"}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleLogout}
                aria-label="Sign out"
              >
                <LogOut className="h-4 w-4 mr-2" aria-hidden="true" />
                <span className="hidden sm:inline">Sign Out</span>
              </Button>
            </div>
          )}
        </div>
      </header>

      <aside
        id="navigation-menu"
        className={`fixed top-0 left-0 h-full w-80 bg-background border-r shadow-2xl z-50 transform transition-transform duration-300 ease-in-out flex flex-col ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        role="navigation"
        aria-label="Main navigation"
      >
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-xl font-bold">Navigation</h2>
          <button
            onClick={() => setIsOpen(false)}
            className="p-2 hover:bg-accent rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
            aria-label="Close navigation menu"
          >
            <X size={24} aria-hidden="true" />
          </button>
        </div>

        <nav
          className="flex-1 p-4 overflow-y-auto"
          aria-label="Main navigation"
        >
          <ul className="space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.to);
              return (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    onClick={() => setIsOpen(false)}
                    className={`flex items-center gap-3 p-3 rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 ${
                      active
                        ? "bg-primary text-primary-foreground"
                        : "hover:bg-accent"
                    }`}
                    aria-current={active ? "page" : undefined}
                  >
                    <Icon size={20} aria-hidden="true" />
                    <span className="font-medium">{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>

          {auth.isAuthenticated && (
            <>
              <Separator className="my-4" />
              <div className="px-3 py-2">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <User className="h-4 w-4" aria-hidden="true" />
                  <span className="font-medium">Signed in as</span>
                </div>
                <p className="text-sm px-3">
                  {auth.user?.profile?.name ||
                    auth.user?.profile?.email ||
                    "User"}
                </p>
              </div>
            </>
          )}
        </nav>
      </aside>

      {/* Overlay when menu is open */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}
    </>
  );
}
