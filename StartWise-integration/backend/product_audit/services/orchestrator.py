from __future__ import annotations

import logging
from typing import Iterable

from .firecrawl_client import FirecrawlClient
from .gemini_client import GeminiClient
from .qdrant_client import QdrantClient
from .schemas import AuditEvidence, AuditSessionState


logger = logging.getLogger(__name__)


class ProductAuditOrchestrator:
    def __init__(self) -> None:
        self.firecrawl = FirecrawlClient()
        self.gemini = GeminiClient()
        self.qdrant = QdrantClient()

    def capabilities(self) -> dict[str, bool]:
        return {
            "gemini": self.gemini.is_configured(),
            "firecrawl": self.firecrawl.is_configured(),
            "qdrant": self.qdrant.is_configured(),
        }

    def run(self, session: AuditSessionState, include_search: bool = True) -> AuditSessionState:
        session.status = "running"
        session.error = None

        self._enrich_attachments(session)
        local_evidence = self._build_local_evidence(session)
        website_evidence: list[AuditEvidence] = []
        if session.website_url:
            scraped = self.firecrawl.scrape(session.website_url)
            if scraped:
                website_evidence.append(scraped)

        external_sources: list[AuditEvidence] = []
        if include_search:
            external_sources = self.firecrawl.search(self._search_query(session), max_results=5)

        knowledge_base = self._chunk_evidence([*local_evidence, *website_evidence])
        session.external_sources = external_sources
        session.indexed_documents = len(knowledge_base)

        retrieved_context = self._retrieve_context(session, knowledge_base)
        session.retrieved_context = retrieved_context

        report = self._generate_report(
            session=session,
            retrieved_context=retrieved_context,
            external_sources=external_sources,
        )
        session.report = report
        session.status = "completed"
        return session

    def _enrich_attachments(self, session: AuditSessionState) -> None:
        if not session.attachments:
            return

        startup_context = (
            f"Startup name: {session.startup_name or 'Unknown'}\n"
            f"Product description: {session.product_description or 'Not provided'}\n"
            f"Audit goal: {session.audit_goal or 'General product and website evaluation'}"
        )

        for attachment in session.attachments:
            if attachment.retrieval_text():
                attachment.extraction_status = attachment.extraction_status or "ready"
                attachment.extraction_error = None
                continue

            if not attachment.base64_data:
                attachment.extraction_status = "empty"
                attachment.extraction_error = "No text or binary payload was provided"
                continue

            if not self.gemini.is_configured():
                attachment.extraction_status = "skipped"
                attachment.extraction_error = "Gemini is not configured for multimodal extraction"
                continue

            try:
                attachment.extracted_text = self.gemini.extract_attachment_text(
                    attachment=attachment,
                    startup_context=startup_context,
                )
                attachment.extraction_status = "ready" if attachment.extracted_text else "empty"
                attachment.extraction_error = None if attachment.extracted_text else "No extractable text returned"
            except Exception as exc:
                logger.warning(
                    "Attachment extraction failed for %s in session %s: %s",
                    attachment.name,
                    session.session_id,
                    exc,
                )
                attachment.extraction_status = "error"
                attachment.extraction_error = str(exc)

    def _build_local_evidence(self, session: AuditSessionState) -> list[AuditEvidence]:
        items: list[AuditEvidence] = []
        summary_lines = []
        if session.startup_name:
            summary_lines.append(f"Startup name: {session.startup_name}")
        if session.product_description:
            summary_lines.append(f"Product description: {session.product_description}")
        if session.audit_goal:
            summary_lines.append(f"Audit goal: {session.audit_goal}")
        if session.website_url:
            summary_lines.append(f"Website URL: {session.website_url}")

        if summary_lines:
            items.append(
                AuditEvidence(
                    id="product-brief",
                    title="Product brief",
                    content="\n".join(summary_lines),
                    source_type="user_input",
                )
            )

        for index, attachment in enumerate(session.attachments):
            text = attachment.retrieval_text()
            if not text:
                continue
            items.append(
                AuditEvidence(
                    id=f"attachment-{index}",
                    title=attachment.name,
                    content=text,
                    source_type="attachment",
                    url=attachment.source_url,
                    metadata={"content_type": attachment.content_type},
                )
            )
        return items

    def _chunk_evidence(self, items: Iterable[AuditEvidence], chunk_size: int = 1400) -> list[AuditEvidence]:
        chunks: list[AuditEvidence] = []
        for item in items:
            content = (item.content or "").strip()
            if not content:
                continue
            if len(content) <= chunk_size:
                chunks.append(item)
                continue

            for index, piece in enumerate(_split_text(content, chunk_size=chunk_size), start=1):
                chunks.append(
                    AuditEvidence(
                        id=f"{item.id}-chunk-{index}",
                        title=f"{item.title} (part {index})",
                        content=piece,
                        source_type=item.source_type,
                        url=item.url,
                        metadata=item.metadata,
                    )
                )
        return chunks

    def _retrieve_context(
        self,
        session: AuditSessionState,
        knowledge_base: list[AuditEvidence],
    ) -> list[AuditEvidence]:
        if not knowledge_base:
            return []
        if not self.gemini.is_configured():
            return knowledge_base[:6]

        try:
            embeddings = self.gemini.embed_texts(
                [item.content for item in knowledge_base],
                titles=[item.title for item in knowledge_base],
            )
        except Exception as exc:
            logger.warning(
                "Embedding generation failed for session %s, using local context: %s",
                session.session_id,
                exc,
            )
            return knowledge_base[:6]
        if len(embeddings) != len(knowledge_base):
            logger.warning(
                "Embedding count mismatch for session %s, falling back to local context",
                session.session_id,
            )
            return knowledge_base[:6]

        collection_name = self.qdrant.collection_name_for_model(self.gemini.embedding_model)
        session.qdrant_collection = collection_name

        if self.qdrant.is_configured():
            try:
                self.qdrant.ensure_collection(collection_name, len(embeddings[0]))
                self.qdrant.upsert(
                    collection_name=collection_name,
                    session_id=session.session_id,
                    items=knowledge_base,
                    vectors=embeddings,
                )
                query_vector = self.gemini.embed_query(self._retrieval_query(session))
                retrieved = self.qdrant.search(
                    collection_name=collection_name,
                    session_id=session.session_id,
                    query_vector=query_vector,
                    limit=6,
                )
                if retrieved:
                    return retrieved
            except Exception as exc:
                logger.warning(
                    "Qdrant retrieval failed for session %s, using local context: %s",
                    session.session_id,
                    exc,
                )

        return knowledge_base[:6]

    def _generate_report(
        self,
        session: AuditSessionState,
        retrieved_context: list[AuditEvidence],
        external_sources: list[AuditEvidence],
    ) -> str:
        if not self.gemini.is_configured():
            return self._mock_report(session, retrieved_context, external_sources)

        prompt = self._build_prompt(session, retrieved_context, external_sources)
        try:
            return self.gemini.generate_report(prompt, attachments=session.attachments)
        except Exception as exc:
            logger.warning("Gemini report generation failed, using heuristic fallback: %s", exc)
            return self._mock_report(session, retrieved_context, external_sources)

    def _build_prompt(
        self,
        session: AuditSessionState,
        retrieved_context: list[AuditEvidence],
        external_sources: list[AuditEvidence],
    ) -> str:
        goal = session.audit_goal or (
            "Evaluate the startup's product, landing page, and website for product weaknesses, "
            "market clarity, trust gaps, conversion friction, and likely technical or operational vulnerabilities."
        )

        context_block = self._format_evidence_block("Retrieved internal context", retrieved_context)
        sources_block = self._format_evidence_block("External research", external_sources)

        return (
            "You are Startwise Product Audit Agent.\n"
            "Analyze the provided product materials and produce an investor-grade but practical audit.\n"
            "Be evidence-led, avoid invented facts, and clearly distinguish unknowns from findings.\n"
            "If the uploaded materials are incomplete, say what is missing instead of guessing.\n\n"
            "Return markdown with exactly these sections:\n"
            "## Audit Snapshot\n"
            "## Product Vulnerabilities\n"
            "## SWOT\n"
            "## Priority Fixes\n"
            "## Open Questions\n"
            "## Evidence Used\n\n"
            "Inside `## Product Vulnerabilities`, cover:\n"
            "- positioning / messaging risk\n"
            "- UX or conversion friction\n"
            "- trust, privacy, or compliance gaps if visible\n"
            "- operational or go-to-market weaknesses\n"
            "- technical blind spots only if supported by the materials\n\n"
            "Inside `## SWOT`, use four flat bullet lists: Strengths, Weaknesses, Opportunities, Threats.\n"
            "Inside `## Priority Fixes`, rank the top 5 fixes from highest leverage to lowest.\n\n"
            f"Startup name: {session.startup_name or 'Unknown'}\n"
            f"Website URL: {session.website_url or 'Not provided'}\n"
            f"Audit goal: {goal}\n"
            f"Product description:\n{session.product_description or 'Not provided'}\n\n"
            f"{context_block}\n\n"
            f"{sources_block}\n"
        )

    def _format_evidence_block(self, heading: str, items: list[AuditEvidence]) -> str:
        if not items:
            return f"{heading}:\n- None"
        lines = [f"{heading}:"]
        for item in items:
            suffix = f" ({item.url})" if item.url else ""
            lines.append(f"- {item.title}{suffix}: {item.content[:800]}")
        return "\n".join(lines)

    def _mock_report(
        self,
        session: AuditSessionState,
        retrieved_context: list[AuditEvidence],
        external_sources: list[AuditEvidence],
    ) -> str:
        strengths = []
        weaknesses = []
        opportunities = []
        threats = []

        if session.product_description:
            strengths.append("There is enough product context to evaluate the offer and intended customer.")
        else:
            weaknesses.append("The product description is sparse, which limits precise diagnosis.")

        if session.website_url:
            strengths.append("A live website URL is available, which supports messaging and landing-page review.")
        else:
            weaknesses.append("No website URL was provided, so landing-page evaluation is incomplete.")

        if session.attachments:
            strengths.append("Uploaded materials give extra context beyond a short text brief.")
        else:
            weaknesses.append("No uploaded artifacts were supplied, so deeper UX and product review remains limited.")

        if external_sources:
            opportunities.append("Fresh web research can be used to sharpen positioning against market expectations.")
        else:
            threats.append("Without external evidence, competitive and market assumptions may remain untested.")

        if retrieved_context:
            opportunities.append("Stored product context can support follow-up audits and retrieval-based comparisons.")

        threats.append("Unclear trust signals, pricing clarity, or onboarding flow could reduce conversion if not audited on-page.")

        fixes = [
            "Clarify the primary user, problem, and promised outcome above the fold.",
            "Audit the landing page for trust signals such as proof, privacy language, and credible calls to action.",
            "Turn uploaded collateral into reusable product facts so future audits can compare versions over time.",
            "Capture competitor and market evidence alongside internal materials before making positioning changes.",
            "Run a focused UX walkthrough of the first-time visitor journey from headline to conversion.",
        ]

        evidence_used = [f"- {item.title}" for item in [*retrieved_context, *external_sources][:8]] or ["- User-provided brief only"]

        return (
            "## Audit Snapshot\n"
            f"The current audit reviewed materials for **{session.startup_name or 'this startup'}** and focused on "
            "product clarity, landing-page quality, trust signals, and execution risk.\n\n"
            "## Product Vulnerabilities\n"
            "- Positioning / messaging risk: The core value proposition should be tested for clarity against a first-time visitor's expectations.\n"
            "- UX or conversion friction: The entry journey should be checked for unclear calls to action, weak proof, and confusing structure.\n"
            "- Trust, privacy, or compliance gaps: Any missing policy links, case studies, testimonials, or contact details will weaken confidence.\n"
            "- Operational or go-to-market weaknesses: The offer may be harder to sell if ICP, pricing, or differentiation are not explicit.\n"
            "- Technical blind spots: Uploaded materials alone rarely prove technical quality, so this remains an open validation area.\n\n"
            "## SWOT\n"
            f"- Strengths: {' '.join(strengths) or 'The startup already has materials we can evaluate.'}\n"
            f"- Weaknesses: {' '.join(weaknesses) or 'Some product details still need to be made more explicit.'}\n"
            f"- Opportunities: {' '.join(opportunities) or 'A sharper audit can improve messaging and conversion.'}\n"
            f"- Threats: {' '.join(threats) or 'Competitors with clearer messaging may win user attention first.'}\n\n"
            "## Priority Fixes\n"
            + "\n".join(f"{index}. {item}" for index, item in enumerate(fixes, start=1))
            + "\n\n## Open Questions\n"
            "- What is the single highest-priority conversion action on the landing page?\n"
            "- Which customer segment is most important right now?\n"
            "- What evidence proves the product works better than alternatives?\n"
            "- Which technical or security guarantees are visible to users today?\n"
            "- What material was not uploaded that would improve the audit?\n\n"
            "## Evidence Used\n"
            + "\n".join(evidence_used)
        )

    def _search_query(self, session: AuditSessionState) -> str:
        parts = [
            session.startup_name,
            session.website_url,
            "product review landing page competitor positioning vulnerabilities",
        ]
        return " ".join(part for part in parts if part)

    def _retrieval_query(self, session: AuditSessionState) -> str:
        if session.audit_goal:
            return session.audit_goal
        return (
            "Find the most relevant product evidence for a SWOT analysis, landing page critique, "
            "website vulnerabilities, trust gaps, and conversion risks."
        )


def _split_text(value: str, chunk_size: int) -> list[str]:
    text = (value or "").strip()
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            split = text.rfind("\n", start, end)
            if split <= start:
                split = text.rfind(" ", start, end)
            if split > start:
                end = split
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        start = max(end, start + 1)
    return chunks


product_audit_orchestrator = ProductAuditOrchestrator()
