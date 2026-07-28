export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = { detail: response.statusText };
    }
    const detail = (payload as { detail?: unknown }).detail;
    const message =
      typeof detail === "string"
        ? detail
        : typeof detail === "object" &&
            detail !== null &&
            "message" in detail
          ? String((detail as { message: unknown }).message)
          : "请求失败，请稍后重试";
    throw new ApiError(response.status, message, detail);
  }
  return response.json() as Promise<T>;
}

export function mutation(method: string, body: unknown): RequestInit {
  return {
    method,
    body: JSON.stringify(body),
  };
}
