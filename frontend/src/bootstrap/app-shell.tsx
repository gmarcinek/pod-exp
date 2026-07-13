import { useEffect, useState } from "react";
import { AppSurface } from "../components/layout/app-surface";
import { AppRouter } from "./app-router";
import type { BootstrapPayload } from "./bootstrap-data";
import {
  getBootstrapData,
  getDebateIdFromPathname,
  getFederationIdFromPathname,
  hasBootstrapPayload,
  parseBootstrapPayload,
  setBootstrapData,
} from "./bootstrap-data";

const BOOTSTRAP_TIMEOUT_MS = 5000;

function getBootstrapEndpoint(bootstrap: BootstrapPayload): string | null {
  switch (bootstrap.route) {
    case "debates":
      return "/api/bootstrap/debates";
    case "editorials":
      return "/api/bootstrap/editorials";
    case "new-debate":
      return "/api/bootstrap/newDebate";
    case "editorial":
      return "/api/bootstrap/editorial";
    case "debate-view": {
      const debateId = getDebateIdFromPathname(
        window.location.pathname,
        bootstrap.appBasePath,
      );

      return debateId
        ? `/api/bootstrap/debate/${encodeURIComponent(debateId)}`
        : null;
    }
    case "federation":
      return null;
    case "federation-view": {
      const federationId = getFederationIdFromPathname(
        window.location.pathname,
        bootstrap.appBasePath,
      );
      return federationId
        ? `/api/bootstrap/federation/${encodeURIComponent(federationId)}`
        : null;
    }
    case "agents":
      return "/api/bootstrap/agents";
    case "home":
    default:
      return "/api/bootstrap/home";
  }
}

function getBootstrapFailureMessage(route: BootstrapPayload["route"]): string {
  switch (route) {
    case "debates":
      return "Nie udało się pobrać archiwum debat w trybie dev. Uruchom Flask backend albo sprawdź, czy `/api/bootstrap/debates` odpowiada lokalnie.";
    case "editorials":
      return "Nie udało się pobrać listy editoriali w trybie dev. Uruchom Flask backend albo sprawdź, czy `/api/bootstrap/editorials` odpowiada lokalnie.";
    case "new-debate":
      return "Nie udało się pobrać placeholdera nowej debaty w trybie dev. Uruchom Flask backend albo sprawdź, czy `/api/bootstrap/newDebate` odpowiada lokalnie.";
    case "editorial":
      return "Nie udało się załadować modułu redakcyjnego w trybie dev. Sprawdź, czy `/api/bootstrap/editorial` odpowiada lokalnie.";
    case "debate-view":
      return "Nie udało się pobrać danych debaty w trybie dev. Uruchom Flask backend albo sprawdź, czy `/api/bootstrap/debate/<debate_id>` odpowiada lokalnie.";
    case "federation":
      return "Nie udało się załadować federacji.";
    case "federation-view":
      return "Nie udało się załadować zapisanej sesji federacji.";
    case "agents":
      return "Nie udało się załadować listy agentów.";
    case "home":
    default:
      return "Nie udało się pobrać danych startowych w trybie dev. Uruchom Flask backend albo sprawdź, czy `/api/bootstrap/home` odpowiada lokalnie.";
  }
}

export function AppShell() {
  const [bootstrap, setBootstrap] = useState<BootstrapPayload>(() =>
    getBootstrapData(),
  );
  const [isBootstrapHydrated, setIsBootstrapHydrated] = useState(() =>
    hasBootstrapPayload(),
  );
  const [bootstrapLoadState, setBootstrapLoadState] = useState<
    "idle" | "loading" | "failed"
  >("idle");
  const bootstrapNeedsServerData = import.meta.env.DEV && !isBootstrapHydrated;
  const bootstrapEndpoint = bootstrapNeedsServerData
    ? getBootstrapEndpoint(bootstrap)
    : null;
  const shouldLoadBootstrap =
    bootstrapNeedsServerData && bootstrapEndpoint !== null;

  useEffect(() => {
    if (!shouldLoadBootstrap || !bootstrapEndpoint) {
      return;
    }

    const endpoint = bootstrapEndpoint;

    let cancelled = false;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(
      () => controller.abort(),
      BOOTSTRAP_TIMEOUT_MS,
    );

    setBootstrapLoadState("loading");

    async function loadBootstrap() {
      try {
        const response = await fetch(endpoint, {
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(
            `Bootstrap request failed with status ${response.status}`,
          );
        }

        const nextBootstrap = parseBootstrapPayload(await response.json());

        if (nextBootstrap.route !== bootstrap.route) {
          throw new Error(
            `Unexpected bootstrap route returned for ${bootstrap.route}.`,
          );
        }

        if (cancelled) {
          return;
        }

        setBootstrapData(nextBootstrap);
        setBootstrap(nextBootstrap);
        setIsBootstrapHydrated(true);
      } catch (error) {
        if (cancelled) {
          return;
        }

        console.error(
          `Failed to load ${bootstrap.route} bootstrap data in dev mode.`,
          error,
        );
        setBootstrapLoadState("failed");
      } finally {
        window.clearTimeout(timeoutId);
      }
    }

    void loadBootstrap();

    return () => {
      cancelled = true;
      controller.abort();
      window.clearTimeout(timeoutId);
    };
  }, [bootstrap.route, bootstrapEndpoint, shouldLoadBootstrap]);

  if (shouldLoadBootstrap && bootstrapLoadState !== "failed") {
    return (
      <AppSurface
        apiBaseUrl={bootstrap.apiBaseUrl}
        currentRoute={bootstrap.route}
      >
        <div>Ładowanie danych startowych…</div>
      </AppSurface>
    );
  }

  if (shouldLoadBootstrap && bootstrapLoadState === "failed") {
    return (
      <AppSurface
        apiBaseUrl={bootstrap.apiBaseUrl}
        currentRoute={bootstrap.route}
      >
        <div>{getBootstrapFailureMessage(bootstrap.route)}</div>
      </AppSurface>
    );
  }

  return (
    <AppSurface
      apiBaseUrl={bootstrap.apiBaseUrl}
      currentRoute={bootstrap.route}
    >
      <AppRouter bootstrap={bootstrap} />
    </AppSurface>
  );
}
