export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

const DEFAULT_TIMEOUT_MS = 15_000;

export interface ApiRequestInit extends RequestInit {
  timeoutMs?: number;
}

export async function api<T>(
  path: string,
  options: ApiRequestInit = {},
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, ...requestOptions } = options;
  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) {
    abortFromCaller();
  } else {
    options.signal?.addEventListener("abort", abortFromCaller, { once: true });
  }
  const timeoutId = globalThis.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  let response: Response;
  try {
    response = await fetch(path, {
      ...requestOptions,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
  } catch (error) {
    if (timedOut) {
      throw new ApiError(
        0,
        "后端响应超时，请确认 FastAPI 正在运行后重试。",
        { code: "BACKEND_TIMEOUT" },
      );
    }
    if (options.signal?.aborted) throw error;
    throw new ApiError(
      0,
      "无法连接后端，请确认 FastAPI 正在运行。",
      {
        code: "BACKEND_UNREACHABLE",
        cause: error instanceof Error ? error.message : String(error),
      },
    );
  } finally {
    globalThis.clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }

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
