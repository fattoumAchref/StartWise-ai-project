"use client";

import dynamic from "next/dynamic";
import { useEffect, useId, useState } from "react";
import { ExternalLink, Loader2, Trash2, Upload } from "lucide-react";

import {
  ProductAuditApiError,
  ProductAuditAttachment,
  ProductAuditService,
  ProductAuditSessionResponse,
} from "@/services/productAudit";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });

type UploadDraft = ProductAuditAttachment & {
  id: string;
  size: number;
};

type ProviderStatus = {
  status: string;
  service: string;
  providers: Record<string, boolean>;
} | null;

function generateSessionId(): string {
  return `audit-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function isTextFile(file: File): boolean {
  const type = file.type.toLowerCase();
  const name = file.name.toLowerCase();
  return (
    type.startsWith("text/") ||
    [
      "application/json",
      "application/ld+json",
      "application/xml",
      "text/csv",
      "text/markdown",
    ].includes(type) ||
    [".txt", ".md", ".json", ".csv", ".html", ".xml"].some((ext) =>
      name.endsWith(ext),
    )
  );
}

async function fileToAttachment(file: File): Promise<UploadDraft> {
  const base64Data = await readFileAsDataUrl(file);
  const text = isTextFile(file) ? await file.text() : undefined;

  return {
    id: `${file.name}-${file.lastModified}-${file.size}`,
    name: file.name,
    content_type: file.type || "application/octet-stream",
    base64_data: base64Data,
    text: text?.trim() || undefined,
    size: file.size,
  };
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error(`Failed to read ${file.name}`));
    reader.readAsDataURL(file);
  });
}

function formatBytes(value: number): string {
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ProductAuditPage() {
  const fileInputId = useId();
  const [startupName, setStartupName] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [productDescription, setProductDescription] = useState("");
  const [auditGoal, setAuditGoal] = useState("");
  const [attachments, setAttachments] = useState<UploadDraft[]>([]);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProductAuditSessionResponse | null>(null);
  const [loadedDraft, setLoadedDraft] = useState(false);

  useEffect(() => {
    ProductAuditService.healthCheck()
      .then((status) => {
        setProviderStatus(status);
        setHealthError(null);
      })
      .catch((err) => {
        const message =
          err instanceof ProductAuditApiError
            ? err.message
            : "Unable to reach the product-audit backend.";
        setHealthError(message);
      });
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const raw = localStorage.getItem("startwise_product_audit_draft");
    if (!raw) {
      return;
    }

    try {
      const draft = JSON.parse(raw) as {
        startup_name?: string;
        website_url?: string;
        product_description?: string;
        audit_goal?: string;
      };
      setStartupName(draft.startup_name || "");
      setWebsiteUrl(draft.website_url || "");
      setProductDescription(draft.product_description || "");
      setAuditGoal(draft.audit_goal || "");
      setLoadedDraft(true);
    } catch {
      setLoadedDraft(false);
    } finally {
      localStorage.removeItem("startwise_product_audit_draft");
    }
  }, []);

  const canSubmit =
    !isSubmitting &&
    Boolean(
      startupName.trim() ||
        websiteUrl.trim() ||
        productDescription.trim() ||
        attachments.length,
    );

  async function handleFilesSelected(fileList: FileList | null) {
    if (!fileList?.length) {
      return;
    }

    try {
      setUploadingFiles(true);
      setError(null);
      const nextItems = await Promise.all(
        Array.from(fileList).map((file) => fileToAttachment(file)),
      );

      setAttachments((current) => {
        const seen = new Set(current.map((item) => item.id));
        const merged = [...current];
        for (const item of nextItems) {
          if (!seen.has(item.id)) {
            merged.push(item);
          }
        }
        return merged;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to process files.");
    } finally {
      setUploadingFiles(false);
    }
  }

  function removeAttachment(id: string) {
    setAttachments((current) => current.filter((item) => item.id !== id));
  }

  async function handleSubmit() {
    if (!canSubmit) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await ProductAuditService.analyze({
        session_id: generateSessionId(),
        startup_name: startupName.trim() || undefined,
        website_url: websiteUrl.trim() || undefined,
        product_description: productDescription.trim() || undefined,
        audit_goal: auditGoal.trim() || undefined,
        include_search: true,
        attachments: attachments.map(({ id, size, ...item }) => item),
      });
      setResult(response);
    } catch (err) {
      const message =
        err instanceof ProductAuditApiError
          ? err.message
          : "Product audit failed. Please try again.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="px-4 lg:px-6">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <Card className="overflow-hidden border-border/60 bg-background/95">
          <CardHeader className="gap-3 border-b border-border/60 bg-gradient-to-r from-slate-50 via-white to-amber-50 dark:from-slate-950 dark:via-slate-950 dark:to-slate-900">
            <CardTitle className="text-2xl">Product Audit</CardTitle>
            <CardDescription className="max-w-3xl text-sm leading-6">
              Upload landing pages, screenshots, PDFs, or a live website URL and
              generate a product evaluation with vulnerabilities, SWOT, and
              prioritized fixes. Uploaded media is first converted into
              retrieval-ready text, then embedded and stored in Qdrant.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-6 py-6 xl:grid-cols-[1.05fr_0.95fr]">
              <div className="space-y-5">
              {loadedDraft ? (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-300">
                  Startup context was prefilled from the onboarding track. Add files or adjust the brief before running the audit.
                </div>
              ) : null}

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    Startup Name
                  </label>
                  <Input
                    value={startupName}
                    onChange={(event) => setStartupName(event.target.value)}
                    placeholder="Startwise"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    Website URL
                  </label>
                  <Input
                    value={websiteUrl}
                    onChange={(event) => setWebsiteUrl(event.target.value)}
                    placeholder="https://your-site.com"
                    type="url"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Product Description
                </label>
                <Textarea
                  value={productDescription}
                  onChange={(event) => setProductDescription(event.target.value)}
                  placeholder="Describe the product, the user, and what the website or landing page is trying to achieve."
                  className="min-h-32"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground">
                  Audit Goal
                </label>
                <Textarea
                  value={auditGoal}
                  onChange={(event) => setAuditGoal(event.target.value)}
                  placeholder="Example: Find conversion risks, trust gaps, and generate a SWOT for investors."
                  className="min-h-24"
                />
              </div>

              <div className="space-y-3 rounded-xl border border-dashed border-border/70 bg-muted/20 p-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">
                      Upload Assets
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Add screenshots, PDFs, pitch material, or text files.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      id={fileInputId}
                      type="file"
                      multiple
                      className="hidden"
                      onChange={(event) => {
                        void handleFilesSelected(event.target.files);
                        event.currentTarget.value = "";
                      }}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        const input = document.getElementById(
                          fileInputId,
                        ) as HTMLInputElement | null;
                        input?.click();
                      }}
                      disabled={uploadingFiles}
                    >
                      {uploadingFiles ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Upload className="h-4 w-4" />
                      )}
                      Add files
                    </Button>
                  </div>
                </div>

                {attachments.length > 0 ? (
                  <div className="space-y-3">
                    {attachments.map((attachment) => (
                      <div
                        key={attachment.id}
                        className="flex flex-col gap-3 rounded-lg border border-border/70 bg-background p-3 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-foreground">
                            {attachment.name}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {attachment.content_type || "application/octet-stream"}{" "}
                            - {formatBytes(attachment.size)}
                          </p>
                          {attachment.text ? (
                            <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                              Text content will be indexed directly.
                            </p>
                          ) : (
                            <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">
                              Media will be processed by Gemini before indexing.
                            </p>
                          )}
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeAttachment(attachment.id)}
                          aria-label={`Remove ${attachment.name}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    No files added yet. You can still run an audit with just a
                    website URL and description.
                  </p>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <Button onClick={() => void handleSubmit()} disabled={!canSubmit}>
                  {isSubmitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Running audit
                    </>
                  ) : (
                    "Run Product Audit"
                  )}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setStartupName("");
                    setWebsiteUrl("");
                    setProductDescription("");
                    setAuditGoal("");
                    setAttachments([]);
                    setResult(null);
                    setError(null);
                  }}
                  disabled={isSubmitting}
                >
                  Reset
                </Button>
              </div>

              {error ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-300">
                  {error}
                </div>
              ) : null}
            </div>

            <div className="space-y-4">
              <Card className="border-border/60 bg-muted/10 py-4">
                <CardHeader className="px-4">
                  <CardTitle className="text-base">Backend Status</CardTitle>
                  <CardDescription>
                    Quick signal that Gemini, Firecrawl, and Qdrant are wired.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 px-4">
                  {healthError ? (
                    <p className="text-sm text-red-600 dark:text-red-400">
                      {healthError}
                    </p>
                  ) : providerStatus ? (
                    <>
                      <div className="grid grid-cols-3 gap-2">
                        {Object.entries(providerStatus.providers).map(
                          ([name, enabled]) => (
                            <div
                              key={name}
                              className="rounded-lg border border-border/60 bg-background px-3 py-2"
                            >
                              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                                {name}
                              </p>
                              <p
                                className={`text-sm font-medium ${
                                  enabled
                                    ? "text-emerald-600 dark:text-emerald-400"
                                    : "text-amber-600 dark:text-amber-400"
                                }`}
                              >
                                {enabled ? "Ready" : "Missing"}
                              </p>
                            </div>
                          ),
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Service: {providerStatus.service}
                      </p>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Checking backend health...
                    </p>
                  )}
                </CardContent>
              </Card>

              <Card className="border-border/60 py-4">
                <CardHeader className="px-4">
                  <CardTitle className="text-base">Latest Audit</CardTitle>
                  <CardDescription>
                    The returned report, indexed document count, and attachment
                    extraction state.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 px-4">
                  {result ? (
                    <>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <div className="rounded-lg border border-border/60 bg-muted/10 px-3 py-3">
                          <p className="text-xs uppercase tracking-wide text-muted-foreground">
                            Indexed Documents
                          </p>
                          <p className="mt-1 text-xl font-semibold text-foreground">
                            {result.indexed_documents}
                          </p>
                        </div>
                        <div className="rounded-lg border border-border/60 bg-muted/10 px-3 py-3">
                          <p className="text-xs uppercase tracking-wide text-muted-foreground">
                            Qdrant Collection
                          </p>
                          <p className="mt-1 break-words text-sm font-medium text-foreground">
                            {result.qdrant_collection || "Not created"}
                          </p>
                        </div>
                      </div>

                      {result.qdrant_collection ? (
                        <div className="flex flex-wrap gap-3">
                          <Button variant="outline" asChild>
                            <a
                              href="http://localhost:6333/dashboard#/collections"
                              target="_blank"
                              rel="noreferrer"
                            >
                              Open Qdrant
                              <ExternalLink className="h-4 w-4" />
                            </a>
                          </Button>
                        </div>
                      ) : null}

                      {result.attachments.length ? (
                        <div className="space-y-2">
                          <p className="text-sm font-medium text-foreground">
                            Attachment ingestion
                          </p>
                          {result.attachments.map((attachment) => (
                            <div
                              key={`${attachment.name}-${attachment.content_type}`}
                              className="rounded-lg border border-border/60 bg-background px-3 py-3"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="text-sm font-medium text-foreground">
                                  {attachment.name}
                                </p>
                                <span className="text-xs text-muted-foreground">
                                  {attachment.extraction_status || "unknown"}
                                </span>
                              </div>
                              {attachment.extraction_error ? (
                                <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                                  {attachment.extraction_error}
                                </p>
                              ) : null}
                              {attachment.extracted_text ? (
                                <p className="mt-2 line-clamp-4 whitespace-pre-wrap text-xs text-muted-foreground">
                                  {attachment.extracted_text}
                                </p>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      ) : null}

                      <div className="prose prose-slate max-w-none dark:prose-invert">
                        <ReactMarkdown>{result.report || ""}</ReactMarkdown>
                      </div>
                    </>
                  ) : (
                    <p className="text-sm leading-6 text-muted-foreground">
                      Run an audit and the report will render here. Once the
                      ingest succeeds, you should also see the collection in
                      Qdrant.
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
