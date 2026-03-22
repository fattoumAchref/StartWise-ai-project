import json
import tempfile
from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="Founder Intake - Llama 3.1",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
  --bg: #0b0b0b;
  --panel: #111111;
  --panel-soft: #171717;
  --border: #2a2a2a;
  --text: #f6f6f6;
  --muted: #a9a9a9;
  --accent: #ffffff;
}

html, body, [class*="css"] {
  font-family: 'Space Grotesk', sans-serif;
  background: radial-gradient(circle at 10% 10%, #1a1a1a 0%, #0b0b0b 45%),
              radial-gradient(circle at 90% 90%, #151515 0%, #0b0b0b 50%);
  color: var(--text);
}

.stApp {
  background: transparent;
}

.block-container {
  max-width: 1200px;
  padding-top: 1.2rem;
}

h1, h2, h3 {
  font-family: 'Space Grotesk', sans-serif;
  letter-spacing: 0.2px;
}

.card {
  background: linear-gradient(180deg, var(--panel-soft) 0%, var(--panel) 100%);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.35);
}

.metric {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: #101010;
  padding: 10px 12px;
}

.mono {
  font-family: 'IBM Plex Mono', monospace;
}

[data-testid="stSidebar"] {
  background: #0f0f0f;
  border-right: 1px solid var(--border);
}

.stButton button {
  background: #f5f5f5;
  color: #0d0d0d;
  border: 1px solid #f5f5f5;
  border-radius: 10px;
  font-weight: 600;
}

.stButton button:hover {
  background: #e6e6e6;
  border-color: #e6e6e6;
}

.stTextArea textarea, .stTextInput input {
  background: #0f0f0f;
  color: #f5f5f5;
  border: 1px solid #2d2d2d;
  border-radius: 10px;
}

hr {
  border-color: var(--border);
}
</style>
""",
    unsafe_allow_html=True,
)


def _safe_json(obj):
    try:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        return obj
    except Exception:
        return str(obj)


def _run_parsing(input_value: str):
    from agent.tools.parser import parse_founder_input
    from agent.tools.validator import validate_financial_context

    context = parse_founder_input(input_value)
    validation = validate_financial_context(context)
    return context, validation


with st.sidebar:
    st.markdown("## Configuration")
    st.markdown("LLM provider: **ESPRIT OpenAI-compatible API**")
    st.markdown("Model: **hosted_vllm/Llama-3.1-70B-Instruct**")
    st.markdown("Base URL: `https://tokenfactory.esprit.tn/api`")
    st.markdown("SSL verify: `False`")
    st.markdown("---")
    mode = st.radio("Input type", ["Free text", "CSV/Excel/PDF"], index=0)

st.markdown("# Founder Intake Parser")
st.markdown("<div class='mono'>Layer 2: Parsing + Validation with Llama 3.1</div>", unsafe_allow_html=True)

left, right = st.columns([1.1, 1.0], gap="large")

with left:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Input")

    payload_value = None

    if mode == "Free text":
        text_input = st.text_area(
            "Founder message (FR/EN)",
            height=260,
            placeholder=(
                "Ex: Nous faisons environ 25k TND de revenus par mois, "
                "50 clients payants, prix moyen 500 TND, cash 120k, "
                "burn autour de 40k, et nous voulons lever en seed round."
            ),
        )
        payload_value = text_input
    else:
        uploaded = st.file_uploader(
            "Upload CSV, Excel, or PDF",
            type=["csv", "xls", "xlsx", "pdf"],
            accept_multiple_files=False,
        )
        if uploaded is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
                tmp.write(uploaded.getbuffer())
                payload_value = tmp.name
            st.caption(f"Temporary file: {payload_value}")

    run = st.button("Run Parsing and Validation", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Status")
    st.markdown("<div class='metric mono'>Ready to parse founder input.</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

if run:
    if not payload_value:
        st.error("Please provide an input before running.")
    else:
        try:
            context, validation = _run_parsing(payload_value)

            c_obj = _safe_json(context)
            v_obj = _safe_json(validation)

            st.markdown("## Results")
            c1, c2 = st.columns(2, gap="large")

            with c1:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.subheader("FinancialContext")
                st.json(c_obj)
                st.markdown("</div>", unsafe_allow_html=True)

            with c2:
                st.markdown("<div class='card'>", unsafe_allow_html=True)
                st.subheader("ValidationResult")
                st.json(v_obj)
                st.markdown("</div>", unsafe_allow_html=True)

            st.download_button(
                label="Download parsed context JSON",
                data=json.dumps(c_obj, ensure_ascii=False, indent=2),
                file_name="financial_context.json",
                mime="application/json",
            )
        except Exception as exc:
            st.error(f"Execution error: {exc}")
            st.info(
                "If this error is about models.data_models, add your colleague file at models/data_models.py so parser and validator can import the shared dataclasses."
            )


if __name__ == "__main__":
    pass
