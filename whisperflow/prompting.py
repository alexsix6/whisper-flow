"""Transcription prompt builder — domain glossary + rolling session context.

The OpenAI transcription API accepts a `prompt` that biases the model toward the
spelling/vocabulary in it (proper nouns, brands, acronyms, jargon). It is a soft
prior, not a dictionary. WhisperFlow combines two sources:

1. A static **domain glossary** (`load_base_prompt`) so the bias is present from
   the very first chunk — configurable via the `WHISPERFLOW_PROMPT` env var, with
   a curated default for an AI-development / automation workflow (ES/EN). Set
   `WHISPERFLOW_PROMPT=""` (or `WHISPERFLOW_GLOSSARY=off`) to disable.
2. The **rolling context** (recent transcribed text) the server already keeps, for
   in-session consistency.

`build_prompt` merges them under a total character budget: the glossary is the
domain anchor and is preserved; the rolling tail fills whatever budget remains.
"""

import os

# Curated default glossary, grounded in the recurring vocabulary of this user's
# projects (verified against enterprise_memory) plus common AI-dev / automation
# terms that ASR frequently mishears. Keep it focused — an over-long prompt gets
# diluted. Override entirely with WHISPERFLOW_PROMPT.
DEFAULT_GLOSSARY = (
    "Vocabulario técnico: WhisperFlow, CMF, ALBA, CREATIA, Nutricereales, "
    "Zaimella, INNATE, Hotmart. BigQuery, Cloud Run, Cloud SQL, GCP, Google Cloud, "
    "Vercel, Supabase, Docker, WSL, Redis, Neo4j, Qdrant, PowerBI, Playwright, "
    "FastAPI, n8n, GitHub, MCP, RAG, GraphRAG, embeddings, vector, fine-tuning, "
    "endpoint, deploy, despliegue, pipeline, workflow, webhook, cron, schema, "
    "dataset, repositorio, commit, branch, contenedor, microservicio, "
    "orquestación, automatización, agente, agentes, prompt, token, "
    "OpenAI, Anthropic, Claude, Codex, Gemini, GPT, Whisper, LLM, API, WebSocket."
)

_OFF_VALUES = {"off", "0", "false", "no", "none", "disabled"}


def load_base_prompt() -> str:
    """Return the static glossary prompt.

    `WHISPERFLOW_PROMPT` overrides the default entirely (set it to your own term
    list). `WHISPERFLOW_GLOSSARY=off` (or `WHISPERFLOW_PROMPT=""`) disables it.
    """
    if os.getenv("WHISPERFLOW_GLOSSARY", "").strip().lower() in _OFF_VALUES:
        return ""
    override = os.getenv("WHISPERFLOW_PROMPT")
    if override is not None:
        return override.strip()
    return DEFAULT_GLOSSARY


def build_prompt(base: str, rolling: str, max_chars: int) -> str:
    """Merge the domain glossary `base` with the `rolling` session context.

    The glossary is the domain anchor and is kept; the most recent tail of the
    rolling context fills the remaining budget. Returns "" when both are empty.
    """
    base = (base or "").strip()
    rolling = (rolling or "").strip()
    if max_chars <= 0:
        return ""
    if not base:
        return rolling[-max_chars:]
    if not rolling:
        return base[:max_chars]
    remaining = max_chars - len(base) - 1  # 1 char for the separating space
    if remaining <= 0:
        return base[:max_chars]
    return f"{base} {rolling[-remaining:]}".strip()
