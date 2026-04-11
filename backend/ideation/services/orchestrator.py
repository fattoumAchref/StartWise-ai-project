import json
import os
import re

from .a2a_client import A2AClient
from .schemas import SessionState, SourceLink


class AgentOrchestrator:
    def __init__(self) -> None:
        self.max_questions = int(os.getenv("MAX_IDEATION_QUESTIONS", "5"))
        self.use_mock = os.getenv("USE_A2A_MOCK", "false").lower() == "true"
        self.use_a2a_streaming = os.getenv("A2A_USE_STREAMING", "false").lower() == "true"

        timeout = float(os.getenv("A2A_TIMEOUT_SECONDS", "90"))
        self.question_agent = A2AClient(
            agent_name="QuestionAgent",
            endpoint=os.getenv("QUESTION_AGENT_URL", "http://localhost:8101"),
            timeout_seconds=timeout,
            streaming_enabled=False,
        )
        self.research_agent = A2AClient(
            agent_name="ResearchAgent",
            endpoint=os.getenv("RESEARCH_AGENT_URL", "http://localhost:8102"),
            timeout_seconds=timeout,
            streaming_enabled=self.use_a2a_streaming,
        )
        self.formulator_agent = A2AClient(
            agent_name="FormulatorAgent",
            endpoint=os.getenv("FORMULATOR_AGENT_URL", "http://localhost:8103"),
            timeout_seconds=timeout,
            streaming_enabled=self.use_a2a_streaming,
        )

    def generate_next_question(self, session: SessionState) -> tuple[str, list[str], list[SourceLink]]:
        if self.use_mock:
            question, keywords = self._mock_next_question(session)
            return question, keywords, []

        history = self._format_history(session)
        founder_profile = self._build_founder_profile(session, history)
        refine_prompt = (
            "You are the Question Agent in ideation mode.\n"
            "Refine the user's startup idea into a concise exploration objective.\n"
            "Anchor the objective in the founder's background, current level, and the latest answer.\n"
            "If the founder is still early or unsure, keep the objective focused on discovery rather than advanced planning.\n"
            "Return plain text only.\n\n"
            f"Original idea:\n{session.description}\n\n"
            f"Founder profile:\n{founder_profile}\n\n"
            f"Conversation history:\n{history}\n"
        )

        try:
            refined_objective = self.question_agent.call_sync(
                refine_prompt,
                context={"session_id": session.session_id, "source": "refine_objective"},
            )
        except Exception:
            refined_objective = session.description.strip()

        research_prompt = (
            "You are the Research Agent.\n"
            "Use web search to produce strategic research notes and question angles.\n"
            "Focus on uncertainties the founder should clarify next based on their background and latest answer.\n"
            "Prefer foundational guidance when the founder seems early-stage or unfamiliar with startup language.\n"
            "Avoid recommending advanced finance or operations topics unless the history shows the founder is ready for them.\n"
            "Return compact bullet points."
            "\n\n"
            f"Objective:\n{refined_objective}\n\n"
            f"Founder profile:\n{founder_profile}\n\n"
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
                research_chunks = [
                    self.research_agent.call_sync(
                        research_prompt,
                        context={"session_id": session.session_id, "target_agent": "formulator_agent"},
                    )
                ]
            except Exception:
                research_chunks = []

        research_notes = "\n".join(research_chunks).strip()
        sources = self._extract_sources(research_notes)

        formulate_prompt = (
            "You are the Formulator Agent.\n"
            "Craft exactly one strategic follow-up question for the founder.\n"
            "Rules:\n"
            "1) Ask one question only.\n"
            "2) It must be answerable in 3-6 sentences.\n"
            "3) It must depend on prior answers.\n"
            "4) Avoid yes/no-only framing.\n"
            "5) Prioritize understanding the founder's background, experience, resources, and idea maturity before advanced business planning.\n"
            "6) If the founder seems beginner, use plain language and avoid unexplained jargon like cash flow, CAC, runway, or burn.\n"
            "7) If a business term is truly needed, explain it in simple words inside the question.\n"
            "8) If the founder does not yet have a clear startup idea, ask about problems they understand, people they know, or skills they can build with.\n"
            "9) The question should feel like the next natural step from the latest answer, not a generic checklist item.\n"
            "Return only the final user-facing question.\n\n"
            f"Refined objective:\n{refined_objective}\n\n"
            f"Founder profile:\n{founder_profile}\n\n"
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
        return question, keywords, sources

    def evaluate_answer(self, session: SessionState, question_index: int, answer: str) -> tuple[bool, str]:
        question = session.questions[question_index].question
        history = self._format_history(session)
        founder_profile = self._build_founder_profile(session, history)

        if self.use_mock:
            return self._mock_evaluate_answer(question, answer)

        prompt = (
            "You are the Question Agent evaluating answer quality for ideation.\n"
            "Decide if answer is specific enough for the current question, relevant, and honest about the founder's context.\n"
            "For early background or discovery questions, accept clear plain-language answers even if they are not operationally detailed.\n"
            "Do not penalize the founder for lacking startup jargon.\n"
            "Return valid JSON only:\n"
            '{"is_satisfactory": true|false, "reason": "short reason"}\n\n'
            f"Question:\n{question}\n\n"
            f"Answer:\n{answer}\n\n"
            f"Founder profile:\n{founder_profile}\n\n"
            f"History:\n{history}\n"
        )
        try:
            raw = self.question_agent.call_sync(
                prompt,
                context={"session_id": session.session_id, "source": "evaluate_answer"},
            )
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
        founder_profile = self._build_founder_profile(session, history)

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
            f"Founder profile:\n{founder_profile}\n\n"
            "Match the founder's likely experience level.\n"
            "If the founder appears beginner, use simple language and concrete examples instead of jargon.\n\n"
            f"Conversation history:\n{history}\n"
        )
        try:
            return self.question_agent.call_sync(
                prompt,
                context={"session_id": session.session_id, "source": "suggest_answer"},
            ).strip()
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
                context={"session_id": session.session_id, "source": "generate_keywords"},
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
            return self.question_agent.call_sync(
                prompt,
                context={"session_id": session.session_id, "source": "generate_summary"},
            ).strip()
        except Exception:
            return self._mock_summary(session)

    def generate_image_prompt(self, business_idea: str, business_summary: str) -> str:
        if self.use_mock:
            return self._mock_image_prompt(business_idea)

        prompt = (
            "You are an art director creating prompts for business hero images.\n"
            "Return one concise prompt only, under 80 words.\n"
            "Make it realistic, modern, professional, and suitable as a website background.\n"
            "Avoid logos, text overlays, UI mockups, watermarks, and overly futuristic imagery.\n\n"
            f"Business idea:\n{business_idea}\n\n"
            f"Business summary:\n{business_summary}\n"
        )
        try:
            raw = self.question_agent.call_sync(prompt)
            cleaned = self._sanitize_image_prompt(raw)
            if cleaned:
                return cleaned
        except Exception:
            pass
        return self._mock_image_prompt(business_idea)

    def _mock_next_question(self, session: SessionState) -> tuple[str, list[str]]:
        history = self._format_history(session)
        profile = self._profile_defaults()
        if history != "(No previous questions yet.)":
            profile = self._parse_profile_response(
                self._safe_json(self._heuristic_profile_payload(session.description, history))
            )

        question_bank = [
            "What is your background with this problem or industry, and what makes you want to build a startup around it now?",
            "From what you shared, what skills, experience, or connections do you already have that could help you start?",
            "Do you already have a startup idea you want to pursue, and if yes, what problem does it solve for people in simple terms?",
            "What part of starting this business feels least familiar to you right now, so we can keep the next steps relevant and easy to follow?",
            "Based on your current experience, what is the smallest first step you feel confident taking in the next two weeks?",
        ]

        if profile["has_startup_idea"] is False:
            question_bank[2] = (
                "What kinds of problems do you understand best from your own experience, work, or community, and who seems to struggle with them most?"
            )
        elif profile["experience_level"] == "advanced":
            question_bank[4] = (
                "Given your experience, what assumption about demand, delivery, or pricing do you most need to test next, and how would you test it?"
            )

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
        if answer_words < 8:
            return False, "The answer is a bit short. Add a little more context so the next question can stay relevant."
        lowered_question = question.lower()
        if any(token in lowered_question for token in ["background", "experience", "familiar", "skills"]):
            return True, "This gives enough background to tailor the next question."
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

    def _mock_image_prompt(self, business_idea: str) -> str:
        return (
            f"professional scene representing {business_idea}, modern workspace, "
            "warm natural lighting, subtle depth, realistic photography, wide hero composition"
        )

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
        question_candidates = re.findall(r"([^?]{20,}\?)", text)
        if question_candidates:
            text = question_candidates[-1].strip()
        if not text:
            return "What is your background with this problem or industry, and what makes you want to build around it now?"
        if not text.endswith("?"):
            text += "?"
        return text

    def _build_founder_profile(self, session: SessionState, history: str) -> str:
        if self.use_mock:
            payload = self._heuristic_profile_payload(session.description, history)
            profile = self._parse_profile_response(self._safe_json(payload))
            return json.dumps(profile, ensure_ascii=True)

        prompt = (
            "You are the Question Agent building a lightweight founder profile for adaptive questioning.\n"
            "Infer only what the history supports.\n"
            "Return valid JSON only with this exact shape:\n"
            '{'
            '"experience_level":"beginner|intermediate|advanced",'
            '"has_startup_idea":true|false|null,'
            '"idea_stage":"none|rough|defined|validated|unknown",'
            '"jargon_level":"plain|mixed|advanced",'
            '"recommended_focus":"short phrase",'
            '"knowledge_gaps":["gap"],'
            '"background_summary":"1 short sentence"'
            '}\n\n'
            "Guidance:\n"
            "- Prioritize the founder's background, confidence level, and startup readiness.\n"
            "- If they seem unfamiliar with business concepts, set jargon_level to plain.\n"
            "- If evidence is missing, use conservative defaults rather than guessing.\n\n"
            f"Original idea:\n{session.description}\n\n"
            f"Conversation history:\n{history}\n"
        )
        try:
            raw = self.question_agent.call_sync(
                prompt,
                context={"session_id": session.session_id, "source": "founder_profile"},
            )
            profile = self._parse_profile_response(self._safe_json(raw))
        except Exception:
            profile = self._parse_profile_response(
                self._safe_json(self._heuristic_profile_payload(session.description, history))
            )
        return json.dumps(profile, ensure_ascii=True)

    def _extract_sources(self, research_notes: str) -> list[SourceLink]:
        items: list[SourceLink] = []
        seen_urls: set[str] = set()
        for line in research_notes.splitlines():
            raw = line.strip()
            if not raw:
                continue
            match = re.search(r"\[Source\]\((https?://[^\)]+)\)", raw)
            if not match:
                continue
            url = match.group(1).strip()
            if not url or url in seen_urls:
                continue
            title = re.sub(r"^\-\s*", "", raw)
            title = re.sub(r"\s*\[Source\]\([^\)]+\)", "", title).strip()
            title = title.strip("*").strip()
            items.append(SourceLink(title=title[:140], url=url))
            seen_urls.add(url)
            if len(items) >= 3:
                break
        return items

    def _profile_defaults(self) -> dict:
        return {
            "experience_level": "beginner",
            "has_startup_idea": None,
            "idea_stage": "unknown",
            "jargon_level": "plain",
            "recommended_focus": "founder background and idea clarity",
            "knowledge_gaps": ["startup basics"],
            "background_summary": "The founder's experience level is still being clarified.",
        }

    def _parse_profile_response(self, payload) -> dict:
        defaults = self._profile_defaults()
        if not isinstance(payload, dict):
            return defaults

        experience_level = str(payload.get("experience_level") or defaults["experience_level"]).lower()
        if experience_level not in {"beginner", "intermediate", "advanced"}:
            experience_level = defaults["experience_level"]

        idea_stage = str(payload.get("idea_stage") or defaults["idea_stage"]).lower()
        if idea_stage not in {"none", "rough", "defined", "validated", "unknown"}:
            idea_stage = defaults["idea_stage"]

        jargon_level = str(payload.get("jargon_level") or defaults["jargon_level"]).lower()
        if jargon_level not in {"plain", "mixed", "advanced"}:
            jargon_level = defaults["jargon_level"]

        has_startup_idea = payload.get("has_startup_idea")
        if not isinstance(has_startup_idea, bool):
            has_startup_idea = None

        knowledge_gaps = payload.get("knowledge_gaps")
        if isinstance(knowledge_gaps, list):
            knowledge_gaps = [str(item).strip() for item in knowledge_gaps if str(item).strip()][:5]
        else:
            knowledge_gaps = defaults["knowledge_gaps"]

        recommended_focus = str(payload.get("recommended_focus") or defaults["recommended_focus"]).strip()
        background_summary = str(payload.get("background_summary") or defaults["background_summary"]).strip()

        return {
            "experience_level": experience_level,
            "has_startup_idea": has_startup_idea,
            "idea_stage": idea_stage,
            "jargon_level": jargon_level,
            "recommended_focus": recommended_focus or defaults["recommended_focus"],
            "knowledge_gaps": knowledge_gaps or defaults["knowledge_gaps"],
            "background_summary": background_summary or defaults["background_summary"],
        }

    def _heuristic_profile_payload(self, description: str, history: str) -> str:
        combined = f"{description}\n{history}".lower()

        has_startup_idea = None
        idea_stage = "unknown"
        if any(token in combined for token in ["no idea", "not sure", "don't have an idea", "do not have an idea"]):
            has_startup_idea = False
            idea_stage = "none"
        elif any(token in combined for token in ["idea", "startup", "app", "platform", "marketplace", "saas"]):
            has_startup_idea = True
            idea_stage = "rough"

        if any(token in combined for token in ["validated", "paying customers", "revenue", "mvp", "launched", "founded"]):
            experience_level = "advanced"
            jargon_level = "advanced"
            if has_startup_idea is True:
                idea_stage = "validated"
        elif any(token in combined for token in ["worked in", "experience", "managed", "built", "developer", "designer", "marketing"]):
            experience_level = "intermediate"
            jargon_level = "mixed"
            if has_startup_idea is True and idea_stage == "rough":
                idea_stage = "defined"
        else:
            experience_level = "beginner"
            jargon_level = "plain"

        knowledge_gaps = ["founder background", "idea clarity"]
        if jargon_level == "plain":
            knowledge_gaps.append("business basics in simple language")
        if has_startup_idea is False:
            knowledge_gaps.append("problem discovery")

        payload = {
            "experience_level": experience_level,
            "has_startup_idea": has_startup_idea,
            "idea_stage": idea_stage,
            "jargon_level": jargon_level,
            "recommended_focus": "adapt the next question to the founder's background and current idea maturity",
            "knowledge_gaps": knowledge_gaps,
            "background_summary": "Use the founder's latest answer to decide whether to stay in discovery mode or move into planning.",
        }
        return json.dumps(payload, ensure_ascii=True)

    def _sanitize_image_prompt(self, value: str) -> str:
        text = re.sub(r"\s+", " ", (value or "").strip())
        text = text.replace("```", "").strip('"').strip("'")
        text = re.sub(r"^[\-\*\d\.\)\s]+", "", text)
        return text[:240].strip()

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
