/**
 * Browser session id + time zone, sent with every API call.
 *
 * In the public demo each browser gets its own throwaway data on the server,
 * keyed by this id (kept in localStorage; no cookies are used because the
 * frontend and backend are on different domains). If storage is unavailable
 * (private mode, blocked site data) an in-memory id is used for this tab.
 */

let memoryId: string | null = null;
const KEY = "feynlist_session";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID().replace(/-/g, "");
  }
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
}

export function getSessionId(): string {
  if (memoryId) return memoryId;
  try {
    const stored = window.localStorage.getItem(KEY);
    if (stored && /^[a-f0-9]{32}$/.test(stored)) {
      memoryId = stored;
      return stored;
    }
    const id = newId();
    window.localStorage.setItem(KEY, id);
    memoryId = id;
    return id;
  } catch {
    memoryId = memoryId ?? newId();
    return memoryId;
  }
}

export function getTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function sessionHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  return { "X-Feynlist-Session": getSessionId(), "X-Feynlist-TZ": getTimeZone() };
}
