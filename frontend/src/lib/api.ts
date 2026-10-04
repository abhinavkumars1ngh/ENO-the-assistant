export function getApiUrl(): string {
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("eno_host_endpoint");
    if (saved && saved.startsWith("http")) return saved.replace(/\/+$/, "");
  }
  return (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");
}

export function getWsUrl(): string {
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("eno_host_endpoint");
    if (saved && saved.startsWith("http")) return saved.replace(/^http/, "ws").replace(/\/+$/, "");
  }
  return (process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000").replace(/\/+$/, "");
}

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export const getHeaders = (token: string): Record<string, string> => ({
  // Only needed when tunnelling through ngrok (local dev); a custom header forces a CORS preflight otherwise.
  ...(getApiUrl().includes("ngrok") ? { "ngrok-skip-browser-warning": "true" } : {}),
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
});

export interface PlanInfo {
  id: "free" | "plus" | "pro";
  label: string;
  price_paise: number;
  currency: string;
  daily_messages: number | null;
  models: string[];
  voice: boolean;
  tagline: string;
}

export interface Account {
  uid: string;
  email: string | null;
  username: string | null;
  role: string;
  plan: "free" | "plus" | "pro";
  plan_label: string;
  daily_limit: number | null;
  used_today: number;
  models: string[];
  voice: boolean;
  capabilities: {
    mode: "local" | "cloud";
    documents: boolean;
    voice_transcription: boolean;
  };
}

export async function fetchAccount(token: string): Promise<Account | null> {
  try {
    const res = await fetch(`${getApiUrl()}/api/me`, { headers: getHeaders(token) });
    if (!res.ok) return null;
    return (await res.json()) as Account;
  } catch {
    return null;
  }
}

export async function fetchPlans(): Promise<{ plans: PlanInfo[]; razorpay_enabled: boolean; test_mode: boolean } | null> {
  try {
    const res = await fetch(`${getApiUrl()}/api/plans`, { headers: getHeaders("") });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export function formatPrice(paise: number, currency = "INR"): string {
  if (paise === 0) return "Free";
  return new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(paise / 100);
}

export interface EndpointInfo {
  status: "online" | "offline";
  endpoint_url: string | null;
  owner_type?: string;
  owner_id?: number;
  seconds_since_heartbeat?: number;
  message?: string;
}

export async function fetchMyEndpoint(token: string): Promise<EndpointInfo | null> {
  try {
    const res = await fetch(`${getApiUrl()}/api/my-endpoint`, { headers: getHeaders(token) });
    if (!res.ok) return null;
    const data = (await res.json()) as EndpointInfo;
    if (data?.endpoint_url && typeof window !== "undefined") {
      localStorage.setItem("eno_host_endpoint", data.endpoint_url);
    }
    return data;
  } catch {
    return null;
  }
}
