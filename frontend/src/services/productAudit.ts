export interface ProductAuditAttachment {
  name: string;
  content_type?: string;
  text?: string;
  summary_text?: string;
  base64_data?: string;
  source_url?: string;
}

export interface ProductAuditRequest {
  session_id: string;
  startup_name?: string;
  product_description?: string;
  website_url?: string;
  audit_goal?: string;
  include_search?: boolean;
  attachments?: ProductAuditAttachment[];
}

export interface ProductAuditEvidence {
  id: string;
  title: string;
  content: string;
  source_type: string;
  url?: string | null;
  score?: number | null;
  metadata?: Record<string, unknown>;
}

export interface ProductAuditSessionResponse {
  session_id: string;
  startup_name: string;
  product_description: string;
  website_url?: string | null;
  audit_goal: string;
  attachments: Array<{
    name: string;
    content_type: string;
    text?: string | null;
    summary_text?: string | null;
    source_url?: string | null;
    has_inline_data: boolean;
    extracted_text?: string | null;
    extraction_status?: string | null;
    extraction_error?: string | null;
  }>;
  report?: string | null;
  indexed_documents: number;
  qdrant_collection?: string | null;
  retrieved_context: ProductAuditEvidence[];
  external_sources: ProductAuditEvidence[];
  status: string;
  error?: string | null;
  created_at: string;
  updated_at: string;
}

const API_BASE_URL = (process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000') + '/product-audit';

export class ProductAuditApiError extends Error {
  constructor(
    message: string,
    public status?: number,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ProductAuditApiError";
  }
}

async function apiRequest<T>(
  endpoint: string,
  method: "GET" | "POST" | "DELETE" = "GET",
  body?: unknown,
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const response = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new ProductAuditApiError(
        (errorData as { detail?: string }).detail || `HTTP ${response.status}: ${response.statusText}`,
        response.status,
        errorData,
      );
    }

    return await response.json();
  } catch (error) {
    if (error instanceof ProductAuditApiError) {
      throw error;
    }
    throw new ProductAuditApiError("Network error or server unavailable", 0, error);
  }
}

export class ProductAuditService {
  static async analyze(
    request: ProductAuditRequest,
  ): Promise<ProductAuditSessionResponse> {
    return apiRequest<ProductAuditSessionResponse>("/product-audit/analyze", "POST", request);
  }

  static async getSession(
    sessionId: string,
  ): Promise<ProductAuditSessionResponse> {
    return apiRequest<ProductAuditSessionResponse>(`/product-audit/session/${sessionId}`);
  }

  static async deleteSession(
    sessionId: string,
  ): Promise<{ message: string }> {
    return apiRequest<{ message: string }>(`/product-audit/session/${sessionId}`, "DELETE");
  }

  static async healthCheck(): Promise<{
    status: string;
    service: string;
    providers: Record<string, boolean>;
  }> {
    return apiRequest("/product-audit/health");
  }
}
