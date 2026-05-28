import type { PropsWithChildren } from "react";
import type { BootstrapRoute } from "../../lib/types/bootstrap";
import { buildAppPath } from "../../bootstrap/backend-config";

type AppSurfaceProps = PropsWithChildren<{
  apiBaseUrl: string;
  currentRoute: BootstrapRoute;
}>;

const navigationItems: Array<{ href: string; label: string; route: BootstrapRoute }> = [
  { href: buildAppPath("/"), label: "Start", route: "home" },
  { href: buildAppPath("/debates"), label: "Debates", route: "debates" },
];

export function AppSurface({ apiBaseUrl, currentRoute, children }: AppSurfaceProps) {
  if (currentRoute === "home") {
    return (
      <div className="app-shell app-shell--home" data-api-base-url={apiBaseUrl}>
        {children}
      </div>
    );
  }

  if (currentRoute === "debates" || currentRoute === "debate-view" || currentRoute === "new-debate") {
    return (
      <div className="app-shell app-shell--plain" data-api-base-url={apiBaseUrl}>
        {children}
      </div>
    );
  }

  return (
    <div className="app-shell" data-api-base-url={apiBaseUrl}>
      <div className="app-shell__frame">
        <header className="app-shell__header">
          <div className="app-shell__brand">
            <p className="app-shell__eyebrow">POD-EXP frontend</p>
            <h1 className="app-shell__title">React bootstrap layer</h1>
            <p className="app-shell__copy">
              Wspólna baza wizualna korzysta już z tokenów i dark theme starego UI, ale pełne migracje ekranów pozostają w kolejnych taskach.
            </p>
          </div>
          <nav className="app-shell__nav" aria-label="Primary">
            {navigationItems.map((item) => {
              const isActive = item.route === currentRoute;

              return (
                <a
                  key={item.href}
                  href={item.href}
                  aria-current={isActive ? "page" : undefined}
                  className="app-shell__link"
                >
                  {item.label}
                </a>
              );
            })}
            <div className="app-shell__status">
              <span className="app-shell__status-label">API</span>
              <span>{apiBaseUrl}</span>
            </div>
          </nav>
        </header>
        <main className="app-shell__body">{children}</main>
      </div>
    </div>
  );
}