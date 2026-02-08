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



flowchart TD
  U[Usuario] --> OW[OpenWebUI]
  OW --> P[Pipelines<br/>API OpenAI-compatible]

  P --> router[router<br/>detect_intent]

  %% Ramas iniciales
  router -->|help| help[help node]
  router -->|ping| ping[ping node]

  router -->|sql / cols / count / time_range| plan_sql[plan_sql<br/>plantillas deterministas]
  router -->|NL libre| llm_generate_sql[llm_generate_sql<br/>Ollama llama3]

  %% Ruta determinista
  plan_sql --> validate_sql_det[validate_sql]
  validate_sql_det -->|OK| run_db[run_db<br/>PostgreSQL]
  validate_sql_det -->|NO| error[error]

  %% Ruta LLM
  llm_generate_sql --> validate_sql_llm[validate_llm_sql]
  validate_sql_llm -->|OK| run_db
  validate_sql_llm -->|NO| error

  %% Común
  run_db --> summarize[summarize<br/>formatear respuesta]
  help --> summarize
  ping --> summarize
  error --> summarize

  summarize --> OUT[Respuesta OpenAI-compatible<br/>stream / no-stream]
  OUT --> OW
