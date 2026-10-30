// API client. The access token lives only in memory (never localStorage), so XSS can't read a stored token.
// The refresh token is an httpOnly, SameSite=Strict cookie scoped to /api/auth that JavaScript can't see.

export type User = {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  account_type: string;
  consent_level: string;
  spend_cap_inr: number;
  is_admin?: boolean;
};

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

const CSRF = { "X-Requested-With": "sara-explorer" };

let accessToken: string | null = null;
let refreshing: Promise<User | null> | null = null;
let onSessionLost: (() => void) | null = null;

export function setSessionLostHandler(fn: () => void) {
  onSessionLost = fn;
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

async function readError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
  } catch {
    /* not JSON */
  }
  return res.status >= 500 ? "Server error. Please try again." : `Request failed (${res.status})`;
}

/** Exchange the refresh cookie for a fresh access token. Concurrent callers share one request. */
export function refreshSession(): Promise<User | null> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch("/api/auth/refresh", { method: "POST", credentials: "same-origin", headers: CSRF });
        if (!res.ok) {
          accessToken = null;
          return null;
        }
        const data = await res.json();
        accessToken = data.access_token;
        return data.user as User;
      } catch {
        return null;
      } finally {
        setTimeout(() => (refreshing = null), 0);
      }
    })();
  }
  return refreshing;
}

async function authedFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const res = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (res.status === 401 && retry) {
    const user = await refreshSession();
    if (user) return authedFetch(path, init, false);
    onSessionLost?.();
  }
  return res;
}

export async function api<T = unknown>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const init: RequestInit = { method: opts.method ?? "GET" };
  if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
    init.headers = { "Content-Type": "application/json" };
  }
  const res = await authedFetch(path, init);
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json() as Promise<T>;
}

export async function authPost<T = unknown>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...CSRF },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json() as Promise<T>;
}

export async function uploadAudio(blob: Blob): Promise<{ text: string }> {
  const form = new FormData();
  const type = blob.type.split(";")[0] || "audio/webm";
  const ext = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
  form.append("audio", new File([blob], `voice.${ext}`, { type }));
  const res = await authedFetch("/api/voice/transcribe", { method: "POST", body: form });
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json();
}

export type StreamEvent =
  | { type: "conversation"; conversation_id: string }
  | { type: "token"; text: string }
  | { type: "step" }
  | { type: "status"; text: string }
  | { type: "card"; card: Card }
  | { type: "error"; text: string }
  | { type: "done"; message_id: string };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Card = { type: string; title?: string; [key: string]: any };

/** POST a chat message and read the Server-Sent Events stream. */
export async function streamChat(
  body: { message: string; conversation_id?: string | null },
  onEvent: (e: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await authedFetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new ApiError(await readError(res), res.status);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          try {
            onEvent(JSON.parse(line.slice(6)));
          } catch {
            /* ignore malformed event */
          }
        }
      }
    }
  }
}
