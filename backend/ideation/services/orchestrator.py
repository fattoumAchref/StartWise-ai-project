import json
import os
import re

from .a2a_client import A2AClient
from .schemas import SessionState


class AgentOrchestrator:
    def __init__(self) -> None:
        self.max_questions = int(os.getenv("MAX_IDEATION_QUESTIONS", "5"))
        self.use_mock = os.getenv("USE_A2A_MOCK", "false").lower() == "true"

        timeout = float(os.getenv("A2A_TIMEOUT_SECONDS", "90"))
        self.question_agent = A2AClient(
            endpoint=os.getenv("QUESTION_AGENT_URL", "http://localhost:8101"),
            timeout_seconds=timeout,
        )
        self.research_agent = A2AClient(
            endpoint=os.getenv("RESEARCH_AGENT_URL", "http://localhost:8102"),
            timeout_seconds=timeout,
        )
        self.formulator_agent = A2AClient(
            endpoint=os.getenv("FORMULATOR_AGENT_URL", "http://localhost:8103"),
            timeout_seconds=timeout,
        )

    def generate_next_question(self, session: SessionState) -> tuple[str, list[str]]:
        if self.use_mock:
            return self._mock_next_question(session)

        history = self._format_history(session)
        refine_prompt = (
            "You are the Question Agent in ideation mode.\n"
            "Refine the user's startup idea into a concise exploration objective.\n"
            "Return plain text only.\n\n"
            f"Original idea:\n{session.description}\n\n"
            f"Conversation history:\n{history}\n"
        )

        try:
            refined_objective = self.question_agent.call_sync(refine_prompt)
        except Exception:
            refined_objective = session.description.strip()

        research_prompt = (
            "You are the Research Agent.\n"
            "Use web search to produce strategic research notes and question angles.\n"
            "Focus on uncertainties the founder should clarify next.\n"
            "Return compact bullet points."
            "\n\n"
            f"Objective:\n{refined_objective}\n\n"
            f"Conversation history:\n{history}\n"
        )

        research_chunks: list[str] = []
        try:
            for event in self.research_agent.stream(
                research_prompt,
                context={"session_id": session.session_id, "target_agent": "formulator_agent"},
            ):
                cleaned = event.strip()
                if cleaned:
                    research_chunks.append(cleaned)
        except Exception:
            # Fallback to sync if SSE is unavailable.
            try:
                research_chunks = [self.research_agent.call_sync(research_prompt)]
            except Exception:
                research_chunks = []

        research_notes = "\n".join(research_chunks).strip()

        formulate_prompt = (
            "You are the Formulator Agent.\n"
            "Craft exactly one strategic follow-up question for the founder.\n"
            "Rules:\n"
            "1) Ask one question only.\n"
            "2) It must be answerable in 3-6 sentences.\n"
            "3) It must depend on prior answers.\n"
            "4) Avoid yes/no-only framing.\n"
            "Return only the final user-facing question.\n\n"
            f"Refined objective:\n{refined_objective}\n\n"
            f"Research notes:\n{research_notes}\n\n"
            f"Conversation history:\n{history}\n"
        )

        formulator_chunks: list[str] = []
        try:
            for chunk in self.formulator_agent.stream(
                formulate_prompt,
                context={"session_id": session.session_id, "source": "research_sse"},
            ):
                cleaned = chunk.strip()
                if cleaned:
                    formulator_chunks.append(cleaned)
        except Exception:
            formulator_chunks = []

        if formulator_chunks:
            question_text = " ".join(formulator_chunks)
        else:
            try:
                question_text = self.formulator_agent.call_sync(
                    formulate_prompt,
                    context={"session_id": session.session_id, "source": "research_sse"},
                )
            except Exception:
                question_text, _ = self._mock_next_question(session)

        question = self._sanitize_question(question_text)
        keywords = self.generate_keywords(question, session)
        return question, keywords

    def evaluate_answer(self, session: SessionState, question_index: int, answer: str) -> tuple[bool, str]:
        question = session.questions[question_index].question
        history = self._format_history(session)

        if self.use_mock:
            return self._mock_evaluate_answer(question, answer)

        prompt = (
            "You are the Question Agent evaluating answer quality for ideation.\n"
            "Decide if answer is specific, actionable, and addresses the question.\n"
            "Return valid JSON only:\n"
            '{"is_satisfactory": true|false, "reason": "short reason"}\n\n'
            f"Question:\n{question}\n\n"
            f"Answer:\n{answer}\n\n"
            f"History:\n{history}\n"
        )
        try:
            raw = self.question_agent.call_sync(prompt)
            parsed = self._safe_json(raw)
            if isinstance(parsed, dict) and "is_satisfactory" in parsed:
                is_ok = bool(parsed.get("is_satisfactory"))
                reason = str(parsed.get("reason") or "").strip()
                if reason:
                    return is_ok, reason
        except Exception:
            pass

        return self._mock_evaluate_answer(question, answer)

    def suggest_answer(self, session: SessionState, question_index: int, selected_keywords: list[str]) -> str:
        question = session.questions[question_index].question
        history = self._format_history(session)

        if self.use_mock:
            return (
                "We will focus on "
                + ", ".join(selected_keywords)
                + " to define a clear initial strategy with measurable assumptions."
            )

        prompt = (
            "You are the Question Agent drafting a suggested answer for the founder.\n"
            "Write 4-6 sentences, practical and concise.\n\n"
            f"Question:\n{question}\n\n"
            f"Selected keywords:\n{', '.join(selected_keywords)}\n\n"
            f"Conversation history:\n{history}\n"
        )
        try:
            return self.question_agent.call_sync(prompt).strip()
        except Exception:
            return (
                "We will use "
                + ", ".join(selected_keywords)
                + " to shape a practical first version and validate the riskiest assumption quickly."
            )

    def generate_keywords(self, question: str, session: SessionState) -> list[str]:
        if self.use_mock:
            return self._mock_keywords(question)

        prompt = (
            "Extract 6 concise keywords for the question below.\n"
            "Return JSON array of strings only.\n\n"
            f"Question: {question}\n"
        )
        try:
            raw = self.question_agent.call_sync(
                prompt,
                context={"session_id": session.session_id},
            )
            parsed = self._safe_json(raw)
            if isinstance(parsed, list):
                cleaned = [str(item).strip() for item in parsed if str(item).strip()]
                if cleaned:
                    return cleaned[:6]
        except Exception:
            pass
        return self._mock_keywords(question)

    def generate_summary(self, session: SessionState) -> str:
        history = self._format_history(session)
        if self.use_mock:
            return self._mock_summary(session)

        prompt = (
            "You are the Client Agent creating a final business ideation summary.\n"
            "Structure it with markdown headings and concise paragraphs.\n"
            "Include: Business Idea, Key Insights, Risks, Next Steps.\n\n"
            f"Original idea:\n{session.description}\n\n"
            f"Q/A history:\n{history}\n"
        )
        try:
            return self.question_agent.call_sync(prompt).strip()
        except Exception:
            return self._mock_summary(session)

    def _mock_next_question(self, session: SessionState) -> tuple[str, list[str]]:
        question_bank = [
            "What specific customer segment has the strongest pain point, and how will you reach them in the first 30 days?",
            "What is your initial pricing logic, and which assumptions must be validated before scaling?",
            "Which competitor alternatives are users choosing today, and what concrete advantage can you prove early?",
            "What operational constraint is most likely to slow delivery, and what mitigation plan do you have?",
            "What metrics will define success in the first 90 days, and how will you collect them?",
        ]
        idx = min(len(session.questions), len(question_bank) - 1)
        question = question_bank[idx]
        return question, self._mock_keywords(question)

    def _mock_keywords(self, question: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z]{4,}", question.lower())
        unique: list[str] = []
        for token in tokens:
            if token in {"what", "which", "will", "your", "have", "with", "that", "from"}:
                continue
            if token not in unique:
                unique.append(token)
            if len(unique) == 6:
                break
        return unique or ["market", "customer", "pricing", "distribution", "competition", "validation"]

    def _mock_evaluate_answer(self, question: str, answer: str) -> tuple[bool, str]:
        answer_words = len(answer.split())
        if answer_words < 12:
            return False, "The answer is too short. Add specifics, assumptions, and execution details."
        if "target" in question.lower() and "customer" not in answer.lower():
            return False, "The answer should explicitly define customer segment and acquisition approach."
        return True, "The answer is specific enough to move to the next strategic question."

    def _mock_summary(self, session: SessionState) -> str:
        lines = [
            "# Business Ideation Summary",
            "",
            "## Business Idea",
            session.description.strip(),
            "",
            "## Key Insights",
        ]
        for idx, q in enumerate(session.questions, start=1):
            lines.append(f"{idx}. **Question:** {q.question}")
            lines.append(f"   **Answer:** {q.response or 'Not answered'}")
        lines.extend(
            [
                "",
                "## Risks",
                "- Demand and pricing assumptions still require live validation.",
                "- Go-to-market efficiency depends on focused channel testing.",
                "",
                "## Next Steps",
                "- Validate the strongest assumption with customer interviews.",
                "- Build an MVP experiment with measurable conversion goals.",
            ]
        )
        return "\n".join(lines)

    def _format_history(self, session: SessionState) -> str:
        if not session.questions:
            return "(No previous questions yet.)"
        rows: list[str] = []
        for idx, item in enumerate(session.questions, start=1):
            rows.append(f"Q{idx}: {item.question}")
            if item.response:
                rows.append(f"A{idx}: {item.response}")
        return "\n".join(rows)

    def _sanitize_question(self, value: str) -> str:
        text = re.sub(r"\s+", " ", (value or "").strip())
        text = text.strip('"').strip("'")
        if not text:
            return "What is the most critical assumption you need to validate first, and how will you test it this week?"
        if not text.endswith("?"):
            text += "?"
        return text

    def _safe_json(self, value: str):
        if not value:
            return None
        raw = value.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, flags=re.DOTALL)
        if fenced:
            raw = fenced.group(1).strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    return None
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except json.JSONDecodeError:
                    return None
        return None


orchestrator = AgentOrchestrator()
