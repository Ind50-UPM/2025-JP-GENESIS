# 2025-JP-GENESIS
Agentic AI for applications

TFM - UPM - Proyecto de desarrollo de Genesis 
Autor: Javier Pajares

## Estructura
Usuario
→ OpenWebUI
→ OpenWebUI Pipelines (API OpenAI-compatible)
→ router (detección de intención)

→ [help | ping]
    → respuesta directa
    → OpenWebUI

→ [sql / cols / count / time_range]
    → plan_sql (SQL determinista)
    → validate_sql (solo SELECT/WITH + LIMIT)
    → run_db (PostgreSQL)
    → summarize
    → OpenWebUI

→ [NL libre]
    → llm_generate_sql (Ollama llama3)
    → validate_llm_sql
    → run_db (PostgreSQL)
    → summarize
    → OpenWebUI

