const VISITOR_ID_KEY = "ruanjiankeshe.visitorId";

function readVisitorId(): string | null {
  try {
    return window.localStorage.getItem(VISITOR_ID_KEY);
  } catch {
    return null;
  }
}

function saveVisitorId(visitorId: string): void {
  try {
    window.localStorage.setItem(VISITOR_ID_KEY, visitorId);
  } catch {
    // The API remains usable when browser storage is disabled.
  }
}

/** Send the stable visitor ID and remember the one assigned by the backend. */
export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const visitorId = readVisitorId();
  if (visitorId && !headers.has("X-Visitor-Id")) {
    headers.set("X-Visitor-Id", visitorId);
  }

  const response = await fetch(input, { ...init, headers });
  const assignedVisitorId = response.headers.get("X-Visitor-Id");
  if (assignedVisitorId) saveVisitorId(assignedVisitorId);
  return response;
}
