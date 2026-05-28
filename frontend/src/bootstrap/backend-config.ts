import { getBootstrapData } from "./bootstrap-data";

export type BackendConfig = {
  apiBaseUrl: string;
  appBasePath: string;
};

export function getBackendConfig(): BackendConfig {
  const { apiBaseUrl, appBasePath } = getBootstrapData();

  return {
    apiBaseUrl,
    appBasePath,
  };
}

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function normalizePath(path: string): string {
  return path.startsWith("/") ? path : `/${path}`;
}

export function buildAppPath(path = "/"): string {
  const { appBasePath } = getBackendConfig();
  const normalizedBase = trimTrailingSlash(appBasePath);
  const normalizedPath = path === "/" ? "" : normalizePath(path);

  return `${normalizedBase}${normalizedPath}` || "/";
}

export function buildApiPath(path: string): string {
  const { apiBaseUrl } = getBackendConfig();
  const normalizedBase = trimTrailingSlash(apiBaseUrl);
  const normalizedPath = normalizePath(path);

  return `${normalizedBase}${normalizedPath}` || normalizedPath;
}