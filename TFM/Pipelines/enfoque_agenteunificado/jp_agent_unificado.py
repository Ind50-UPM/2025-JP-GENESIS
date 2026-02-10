import re
import json
import time
import uuid
import unicodedata
from typing import TypedDict, Literal, Dict, Any, Tuple, List

import requests

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_OK = True
except Exception as e:
    psycopg2 = None
    PSYCOPG2_OK = False
    PSYCOPG2_ERR = str(e)

PG_HOST = "138.100.82.184"
PG_PORT = 2345
PG_DB = "ncorrea"
PG_USER = "lectura"
PG_PASS = "ncorrea#2022"

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_CHARS_OUT = 12000

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|call|execute|do)\b",
    re.IGNORECASE,
)
HAS_LIMIT = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)

OLLAMA_URL = "http://172.17.0.1:11434"
OLLAMA_MODEL = "llama3:latest"

SYSTEM_SQL_PROMPT = f"""
Eres un generador de SQL para PostgreSQL. Devuelve SOLO SQL, sin explicaciones, sin markdown.
Reglas:
- SOLO SELECT o WITH.
- PROHIBIDO: INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT/REVOKE/CALL/EXECUTE/DO.
- Para conteos usa COUNT(*).
- Para rangos temporales en time_record usa la columna ts.
- Añade LIMIT {DEFAULT_LIMIT} si corresponde.
- Si faltan nombres exactos, usa information_schema (solo lectura).
""".strip()

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_OK = True
except Exception as e:
    LANGGRAPH_OK = False
    LANGGRAPH_ERR = str(e)


def strip_accents(s: str) -> str:
    s = s or ""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def is_readonly(sql: str) -> Tuple[bool, str]:
    s = (sql or "").strip().strip(";").lstrip()
    if not s:
        return False, "SQL vacío."
    if FORBIDDEN_SQL.search(s):
        return False, "SQL no permitido (solo SELECT/WITH)."
    first = s.split(None, 1)[0].lower()
    if first not in {"select", "with"}:
        return False, f"Solo lectura. Primer token: {first}"
    return True, "ok"


def normalize_limit(sql: str, default_limit: int = DEFAULT_LIMIT) -> str:
    s = (sql or "").strip().strip(";")
    if not s:
        return s
    if HAS_LIMIT.search(s):
        s = re.sub(
            r"\blimit\s+(\d+)\b",
            lambda m: f"LIMIT {min(int(m.group(1)), MAX_LIMIT)}",
            s,
            flags=re.IGNORECASE,
        )
        return s + ";"
    return s + f" LIMIT {default_limit};"


def clip_out(text: str) -> str:
    if len(text) <= MAX_CHARS_OUT:
        return text
    return text[:MAX_CHARS_OUT] + "\n…(salida recortada)…"


def run_sql(sql: str, limit_fetch: int = MAX_LIMIT) -> Dict[str, Any]:
    if not PSYCOPG2_OK:
        return {"ok": False, "error": f"psycopg2 no disponible: {PSYCOPG2_ERR}", "sql": sql}

    ok, reason = is_readonly(sql)
    if not ok:
        return {"ok": False, "error": reason, "sql": sql}

    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            dbname=PG_DB,
            user=PG_USER,
            password=PG_PASS,
            connect_timeout=8,
        )
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            try:
                rows = cur.fetchall()
            except psycopg2.ProgrammingError:
                rows = []
        conn.close()
        return {"ok": True, "rows": rows[:limit_fetch], "row_count": len(rows), "sql": sql}
    except Exception as e:
        return {"ok": False, "error": str(e), "sql": sql}


def fmt_rows(rows: List[Dict[str, Any]], max_rows: int = 15) -> str:
    if not rows:
        return "Sin filas."
    rows = rows[:max_rows]
    cols = list(rows[0].keys())
    out = [" | ".join(cols), "-+-".join(["-" * len(c) for c in cols])]
    for r in rows:
        out.append(" | ".join(str(r.get(c, "")) for c in cols))
    return "\n".join(out)


def ollama_generate_sql(question: str) -> Dict[str, Any]:
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_SQL_PROMPT},
                {"role": "user", "content": question.strip()},
            ],
            "stream": False,
            "options": {"temperature": 0.0},
        }
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=45)
        if r.status_code != 200:
            return {"ok": False, "error": f"Ollama HTTP {r.status_code}: {r.text[:300]}"}
        data = r.json()
        content = (data.get("message", {}) or {}).get("content", "") or ""
        sql = content.strip()
        sql = re.sub(r"^```sql\s*", "", sql, flags=re.IGNORECASE).strip()
        sql = re.sub(r"^```\s*", "", sql).strip()
        sql = re.sub(r"\s*```$", "", sql).strip()
        return {"ok": True, "sql": sql}
    except Exception as e:
        return {"ok": False, "error": str(e)}


COUNT_PAT = re.compile(r"\b(cuantas|count|numero)\b.*\b(filas|registros)\b", re.IGNORECASE)
LAST_HOURS_PAT = re.compile(r"\bultim(as|os)\s+(\d+)\s*(h|horas)\b", re.IGNORECASE)
DATE_RANGE_PAT = re.compile(r"\bentre\s+(\d{4}-\d{2}-\d{2})\s+y\s+(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)
TABLE_PAT = re.compile(r"\b(en|de|del)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", re.IGNORECASE)

DEFAULT_TABLE = "machine_activity"


def extract_table(text_raw: str) -> str:
    text = strip_accents(text_raw).lower()
    m = TABLE_PAT.search(text)
    return m.group(2) if m else DEFAULT_TABLE


def detect_intent(text_raw: str) -> Literal["help", "ping", "sql", "cols", "count", "time_range", "llm_sql"]:
    raw = (text_raw or "").strip()
    low = strip_accents(raw).lower()

    if low in {"help", "ayuda"}:
        return "help"
    if low in {"ping", "test", "test db"}:
        return "ping"
    if low.startswith("sql:"):
        return "sql"
    if low.startswith("cols:") or low.startswith("columnas:"):
        return "cols"

    if DATE_RANGE_PAT.search(low) or LAST_HOURS_PAT.search(low):
        return "time_range"
    if COUNT_PAT.search(low):
        return "count"

    return "llm_sql"


class AgentState(TypedDict, total=False):
    user_text: str
    intent: Literal["help", "ping", "sql", "cols", "count", "time_range", "llm_sql"]
    table: str
    sql: str
    llm_sql: str
    db_result: Dict[str, Any]
    answer: str


def node_router(state: AgentState) -> AgentState:
    txt = state.get("user_text", "") or ""
    return {"intent": detect_intent(txt), "table": extract_table(txt)}


def node_help(state: AgentState) -> AgentState:
    msg = (
        "Comandos:\n"
        "- help\n"
        "- ping\n"
        "- sql: <SELECT/WITH ...>\n"
        "- cols: <tabla>\n\n"
        "Ejemplos:\n"
        "- cuántas filas hay en time_record\n"
        "- últimas 24 horas en time_record\n"
        "- entre 2025-01-01 y 2025-02-01 en time_record\n"
        "- muéstrame 5 filas de time_record\n"
        f"\nLLM: {OLLAMA_MODEL}"
    )
    return {"answer": msg}


def node_ping(state: AgentState) -> AgentState:
    r = run_sql("SELECT 1 AS ok;", limit_fetch=1)
    return {"answer": "✅ DB OK (SELECT 1)" if r.get("ok") else f"❌ {r.get('error')}"}


def node_plan_sql(state: AgentState) -> AgentState:
    intent = state.get("intent", "llm_sql")
    table = state.get("table", DEFAULT_TABLE)
    txt = state.get("user_text", "") or ""
    low = strip_accents(txt).lower().strip()

    full_table = f"public.{table}"

    if intent == "sql":
        raw = txt.split(":", 1)[1].strip()
        return {"sql": normalize_limit(raw)}

    if intent == "cols":
        parts = txt.split(":", 1)
        tname = parts[1].strip() if len(parts) > 1 and parts[1].strip() else table
        sql = (
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            f"WHERE table_schema='public' AND table_name='{tname}' "
            "ORDER BY ordinal_position;"
        )
        return {"sql": sql}

    if intent == "count":
        return {"sql": f"SELECT COUNT(*) AS n FROM {full_table};"}

    if intent == "time_range":
        if table != "time_record":
            full_table = "public.time_record"

        m = DATE_RANGE_PAT.search(low)
        if m:
            a, b = m.group(1), m.group(2)
            return {"sql": f"SELECT COUNT(*) AS n FROM {full_table} WHERE ts BETWEEN '{a}' AND '{b}';"}

        m2 = LAST_HOURS_PAT.search(low)
        if m2:
            hours = max(1, min(int(m2.group(2)), 168))
            return {"sql": f"SELECT COUNT(*) AS n FROM {full_table} WHERE ts >= NOW() - INTERVAL '{hours} hours';"}

        return {"sql": f"SELECT * FROM {full_table} LIMIT 10;"}

    return {"sql": ""}


def node_llm_generate_sql(state: AgentState) -> AgentState:
    question = state.get("user_text", "") or ""
    gen = ollama_generate_sql(question)
    if not gen.get("ok"):
        return {"llm_sql": "", "answer": f"❌ Error LLM: {gen.get('error')}"}
    return {"llm_sql": gen.get("sql", "").strip()}


def node_validate_llm_sql(state: AgentState) -> AgentState:
    sql = (state.get("llm_sql") or "").strip()
    if not sql:
        return {"answer": "❌ El LLM no devolvió SQL."}

    ok, reason = is_readonly(sql)
    if not ok:
        return {"answer": f"❌ SQL no permitido: {reason}\n\nSQL:\n{sql}"}

    return {"sql": normalize_limit(sql)}


def node_run_db(state: AgentState) -> AgentState:
    sql = state.get("sql", "")
    if not sql:
        return {"db_result": {"ok": True, "rows": [], "sql": ""}}
    return {"db_result": run_sql(sql)}


def node_summarize(state: AgentState) -> AgentState:
    if state.get("answer"):
        return {"answer": state["answer"]}

    intent = state.get("intent", "llm_sql")
    res = state.get("db_result", {})

    if not res.get("ok"):
        return {"answer": f"❌ Error DB: {res.get('error')}\nSQL:\n{res.get('sql','')}"}

    rows = res.get("rows", [])
    sql_used = res.get("sql", "")

    if rows and isinstance(rows[0], dict) and "n" in rows[0]:
        return {"answer": f"✅ Resultado\nIntent: {intent}\nSQL:\n{sql_used}\n\nn = {rows[0]['n']}"}

    out = (
        f"✅ Resultado\nIntent: {intent}\nSQL:\n{sql_used}\n\n"
        f"```text\n{fmt_rows(rows)}\n```"
    )
    return {"answer": clip_out(out)}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("router", node_router)
    g.add_node("help", node_help)
    g.add_node("ping", node_ping)
    g.add_node("plan_sql", node_plan_sql)
    g.add_node("llm_generate_sql", node_llm_generate_sql)
    g.add_node("validate_llm_sql", node_validate_llm_sql)
    g.add_node("run_db", node_run_db)
    g.add_node("summarize", node_summarize)

    g.set_entry_point("router")

    def route_from_router(state: AgentState) -> str:
        i = state.get("intent", "llm_sql")
        if i == "help":
            return "help"
        if i == "ping":
            return "ping"
        if i in {"sql", "cols", "count", "time_range"}:
            return "plan_sql"
        return "llm_generate_sql"

    g.add_conditional_edges("router", route_from_router, {
        "help": "help",
        "ping": "ping",
        "plan_sql": "plan_sql",
        "llm_generate_sql": "llm_generate_sql",
    })

    g.add_edge("help", "summarize")
    g.add_edge("ping", "summarize")

    g.add_edge("plan_sql", "run_db")
    g.add_edge("run_db", "summarize")

    g.add_edge("llm_generate_sql", "validate_llm_sql")
    g.add_edge("validate_llm_sql", "run_db")

    g.add_edge("summarize", END)
    return g.compile()


GRAPH = build_graph() if LANGGRAPH_OK else None


class Pipeline:
    id = "jp_agent_unificado"
    name = "JP - Agente Unificado (LangGraph + llama3 + BBDD)"

    def _wrap_nonstream(self, msg: str):
        return {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.id,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": msg}, "finish_reason": "stop"}],
        }

    def _sse_stream(self, msg: str):
        chunk_id = f"chatcmpl-{uuid.uuid4()}"
        created = int(time.time())
        first = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": self.id,
            "choices": [{"index": 0, "delta": {"content": msg}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(first, ensure_ascii=False)}\n\n"
        last = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": self.id,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(last, ensure_ascii=False)}\n\n"

    def pipe(self, body: dict, **kwargs):
        if not LANGGRAPH_OK:
            msg = f"❌ LangGraph no disponible: {LANGGRAPH_ERR}"
            return self._sse_stream(msg) if body.get("stream") else self._wrap_nonstream(msg)

        try:
            messages = body.get("messages", [])
            user_text = (messages[-1].get("content") if messages else "") or ""
            out = GRAPH.invoke({"user_text": user_text})
            ans = out.get("answer", "Sin respuesta.")
            return self._sse_stream(ans) if body.get("stream") else self._wrap_nonstream(ans)
        except Exception as e:
            msg = f"❌ Error interno: {e}"
            return self._sse_stream(msg) if body.get("stream") else self._wrap_nonstream(msg)

