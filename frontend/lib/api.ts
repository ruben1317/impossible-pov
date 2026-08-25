export const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {"Content-Type": "application/json", ...(init?.headers || {})},
    cache: "no-store",
  });
  if (!res.ok) {
    const raw = await res.text();
    let message = raw || `Request failed (${res.status})`;
    try {
      const parsed = JSON.parse(raw);
      message = parsed?.detail || parsed?.message || message;
    } catch {}
    throw new Error(message);
  }
  return res.json();
}
