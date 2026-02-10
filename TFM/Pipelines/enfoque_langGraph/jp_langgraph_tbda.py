import re
import json
import time
import uuid
import unicodedata
from typing import TypedDict, Literal, Dict, Any, Tuple

# ---- Postgres
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
PG_DB   = "ncorrea"
PG_USER = "lectura"
PG_PASS = "ncorrea#2022"

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|call|execute|do)\b",
    re.IGNORECASE,
)

# ---- LangGraph
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_OK = True
except Exception as e:
    LANGGRAPH_OK = False
    LANGGRAPH_ERR = str(e)


# ---------- Util: quitar tildes ----------
def strip_accents(s: str) -> str:
    s = s or ""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# ---------- helpers SQL ----------
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
    if re.search(r"\blimit\s+\d+\b", s, flags=re.IGNORECASE):
        s = re.sub(
            r"\blimit\s+(\d+)\b",
            lambda m: f"LIMIT {min(int(m.group(1)), MAX_LIMIT)}",
            s,
            flags=re.IGNORECASE
        )
        return s + ";"
    return s + f" LIMIT {default_limit};"

def run_sql(sql: str, limit_fetch: int = MAX_LIMIT) -> Dict[str, Any]:
    if not PSYCOPG2_OK:
        return {"ok": False, "error": f"psycopg2 no disponible: {PSYCOPG2_ERR}", "sql": sql}

    ok, reason = is_readonly(sql)
    if not ok:
        return {"ok": False, "error": reason, "sql": sql}

    try:
        conn = psycopg2.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS,
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

def fmt_rows(rows, max_rows: int = 15) -> str:
    if not rows:
        return "Sin filas."
    rows = rows[:max_rows]
    cols = list(rows[0].keys())
    lines = []
    lines.append(" | ".join(cols))
    lines.append("-+-".join(["-" * len(c) for c in cols]))
    for r in rows:
        lines.append(" | ".join(str(r.get(c, "")) for c in cols))
    return "\n".join(lines)


# ---------- NL parsing (usa texto SIN tildes) ----------
COUNT_PAT = re.compile(r"\b(cuantas|count|numero)\b.*\b(filas|registros)\b", re.IGNORECASE)
LAST_HOURS_PAT = re.compile(r"\bultim(as|os)\s+(\d+)\s*(h|horas)\b", re.IGNORECASE)
DATE_RANGE_PAT = re.compile(r"\bentre\s+(\d{4}-\d{2}-\d{2})\s+y\s+(\d{4}-\d{2}-\d{2})\b", re.IGNORECASE)
TABLE_PAT = re.compile(r"\b(en|de|del)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", re.IGNORECASE)

DEFAULT_TABLE = "machine_activity"

def extract_table(text_raw: str) -> str:
    # extraemos tabla usando texto sin tildes (para que "en" etc. funcione igual)
    text = strip_accents(text_raw).lower()
    m = TABLE_PAT.search(text)
    if m:
        return m.group(2)
    return DEFAULT_TABLE

def detect_intent(text_raw: str) -> Literal["sql", "cols", "count", "time_range", "direct"]:
    raw = (text_raw or "").strip()
    low = strip_accents(raw).lower()

    if low.startswith("sql:"):
        return "sql"
    if low.startswith("cols:") or low.startswith("columnas:"):
        return "cols"

    if DATE_RANGE_PAT.search(low) or LAST_HOURS_PAT.search(low):
        return "time_range"
    if COUNT_PAT.search(low):
        return "count"
    return "direct"


# ---------- LangGraph State ----------
class AgentState(TypedDict, total=False):
    user_text: str
    intent: Literal["sql", "cols", "count", "time_range", "direct"]
    table: str
    sql: str
    db_result: Dict[str, Any]
    answer: str


def node_router(state: AgentState) -> AgentState:
    txt = state.get("user_text", "") or ""
    intent = detect_intent(txt)
    table = extract_table(txt)
    return {"intent": intent, "table": table}

def node_plan_sql(state: AgentState) -> AgentState:
    intent = state.get("intent", "direct")
    table = state.get("table", DEFAULT_TABLE)
    txt = state.get("user_text", "") or ""
    low = strip_accents(txt).lower().strip()

    full_table = f"public.{table}"

    if intent == "sql":
        raw = txt.split(":", 1)[1].strip()
        safe = normalize_limit(raw)
        return {"sql": safe}

    if intent == "cols":
        parts = txt.split(":", 1)
        tname = parts[1].strip() if len(parts) > 1 and parts[1].strip() else table
        # Nota: puede devolver vacío por permisos; tu sql manual funciona si el usuario lo permite
        sql = (
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            f"WHERE table_schema='public' AND table_name='{tname}' "
            "ORDER BY ordinal_position;"
        )
        return {"sql": sql}

    if intent == "count":
        sql = f"SELECT COUNT(*) AS n FROM {full_table};"
        return {"sql": sql}

    if intent == "time_range":
        # si no especifica time_record, forzamos time_record (por ahora)
        if table != "time_record":
            full_table = "public.time_record"

        m = DATE_RANGE_PAT.search(low)
        if m:
            a, b = m.group(1), m.group(2)
            sql = f"SELECT COUNT(*) AS n FROM {full_table} WHERE ts BETWEEN '{a}' AND '{b}';"
            return {"sql": sql}

        m2 = LAST_HOURS_PAT.search(low)
        if m2:
            hours = max(1, min(int(m2.group(2)), 168))
            sql = f"SELECT COUNT(*) AS n FROM {full_table} WHERE ts >= NOW() - INTERVAL '{hours} hours';"
            return {"sql": sql}

        return {"sql": f"SELECT * FROM {full_table} LIMIT 10;"}

    return {"sql": ""}

def node_run_db(state: AgentState) -> AgentState:
    sql = state.get("sql", "")
    if not sql:
        return {"db_result": {"ok": True, "rows": [], "sql": ""}}
    res = run_sql(sql)
    return {"db_result": res}

def node_summarize(state: AgentState) -> AgentState:
    intent = state.get("intent", "direct")
    txt = state.get("user_text", "")
    res = state.get("db_result", {})

    if intent == "direct":
        return {"answer": (
            "Ruta DIRECTA.\n"
            f"Mensaje: {txt}\n\n"
            "Usa:\n"
            "- `sql: ...`\n"
            "- `cols: time_record`\n"
            "- `cuántas filas hay en machine_activity`\n"
            "- `últimas 24 horas en time_record`\n"
            "- `entre 2025-01-01 y 2025-02-01 en time_record`"
        )}

    if not res.get("ok"):
        return {"answer": f"❌ Error DB: {res.get('error')}\nSQL:\n{res.get('sql','')}"}

    rows = res.get("rows", [])

    if rows and isinstance(rows[0], dict) and "n" in rows[0]:
        return {"answer": f"✅ Resultado\nIntent: {intent}\nSQL:\n{res.get('sql')}\n\nn = {rows[0]['n']}"}

    return {"answer": f"✅ Resultado\nSQL:\n{res.get('sql')}\n\n```text\n{fmt_rows(rows)}\n```"}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("router", node_router)
    g.add_node("plan_sql", node_plan_sql)
    g.add_node("run_db", node_run_db)
    g.add_node("summarize", node_summarize)

    g.set_entry_point("router")
    g.add_edge("router", "plan_sql")
    g.add_edge("plan_sql", "run_db")
    g.add_edge("run_db", "summarize")
    g.add_edge("summarize", END)

    return g.compile()

GRAPH = build_graph() if LANGGRAPH_OK else None


class Pipeline:
    id = "jp_langgraph_tbda"
    name = "JP - LangGraph (tildes OK, count + time range)"

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
            msg = f"❌ LangGraph no disponible: {LANGGRAPH_ERR}\nInstalar paquete `langgraph` en Pipelines."
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


