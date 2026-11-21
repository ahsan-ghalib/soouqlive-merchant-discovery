import { clearSession, getAccessToken, getRefreshToken, setSession } from "@/lib/auth";
import type { ApiResponse } from "@/types/api";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

type RequestOptions = {
  method?: string;
  body?: unknown;
  auth?: boolean;
  query?: Record<string, string | number | boolean | undefined | null>;
};

function buildUrl(path: string, query?: RequestOptions["query"]) {
  const url = new URL(path.startsWith("http") ? path : `${API_BASE}${path}`);
  if (query) {
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }
  return url.toString();
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  const res = await fetch(buildUrl("/auth/refresh"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) {
    clearSession();
    return null;
  }
  const json = (await res.json()) as ApiResponse<{
    access_token: string;
    refresh_token: string;
    token_type: string;
  }>;
  const userRaw = localStorage.getItem("soouq_user");
  const user = userRaw ? JSON.parse(userRaw) : null;
  if (user) {
    setSession(json.data, user);
  }
  return json.data.access_token;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiResponse<T>> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const useAuth = options.auth !== false;
  let token = getAccessToken();
  if (useAuth && token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let res = await fetch(buildUrl(path, options.query), {
    method: options.method || (options.body ? "POST" : "GET"),
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 401 && useAuth) {
    token = await refreshAccessToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
      res = await fetch(buildUrl(path, options.query), {
        method: options.method || (options.body ? "POST" : "GET"),
        headers,
        body: options.body ? JSON.stringify(options.body) : undefined,
      });
    }
  }

  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail =
      typeof json?.detail === "string"
        ? json.detail
        : json?.message || `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return json as ApiResponse<T>;
}
