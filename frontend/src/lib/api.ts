const apiBaseUrl = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000/api/v1').replace(/\/$/, '');
const apiOrigin = apiBaseUrl.replace(/\/api\/v1$/, '');

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init.headers },
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(result.error?.message ?? `Request failed (${response.status}).`);
    Object.assign(error, { status: response.status });
    throw error;
  }
  return result.data as T;
}

export type SessionAccount = {
  id: string;
  role: 'customer' | 'admin';
  email: string;
  profile: { id: string; firstName: string; lastName: string; phone: string; businessName: string; industry: string } | null;
};

export function getServiceHealth() {
  return fetch(`${apiOrigin}/api/health`, { cache: 'no-store' }).then(async (response) => {
    const result = await response.json();
    if (!response.ok) throw new Error(result.error?.message ?? `Health check failed (${response.status}).`);
    return result.data as { status: string; database: string; assistant: string };
  });
}
