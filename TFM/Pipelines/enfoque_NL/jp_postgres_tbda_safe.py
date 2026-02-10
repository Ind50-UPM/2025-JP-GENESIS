import re
import json
import time
import uuid
import unicodedata
from typing import List, Dict, Any, Tuple

import requests

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_OK = True
except Exception as e:
    psycopg2 = None
    PSYCOPG2_OK = False
    PSYCOPG2_ERR = str(e)

# ---- TBDA (solo lectura)
PG_HOST = "138.100.82.184"
PG_PORT = 2345
PG_DB   = "ncorrea"
PG_USER = "lectura"
PG_PASS = "ncorrea#2022"

# ---- Ollama
OLLAMA_URL = "http://172.17.0.1:11434"   # si falla, prueba "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3:latest"           # o mistral:latest / deepseek-r1:latest

# ---- Seguridad/Límites
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_CHARS_OUT = 12000

FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|call|execute|do)\b",
    re.IGNORECASE,
)
HAS_LIMIT = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)

SYSTEM_SQL_PROMPT = f"""
Eres un generador de SQL para PostgreSQL. Devuelve SOLO SQL, sin explicaciones.
Reglas estrictas:
- SOLO consultas de lectura: SELECT o WITH.
- PROHIBIDO: INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT/REVOKE/CALL/EXECUTE/DO.
- Si el usuario pide "cuántas filas hay en <tabla>", usa: SELECT COUNT(*) AS n FROM public.<tabla>;
- Si el usuario pide "tablas", usa information_schema.tables.
- Si dudas del esquema, consulta information_schema (solo lectura).
- Para listados, añade LIMIT {DEFAULT_LIMIT} si no hay LIMIT.
Devuelve SQL válido para PostgreSQL.
""".strip()


# -------------------------
# Utilidades texto (NL)
# -------------------------
def strip_accents(s: str) -> str:
    s = s or ""
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# Patrones NL (deterministas)
COUNT_ROWS_PAT = re.compile(
    r"\b(cuantas|cuantas|numero|número|count)\b.*\b(filas|registros)\b",
    re.IGNORECASE
)
TABLE_IN_TEXT_PAT = re.compile(r"\b(en|de|del)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", re.IGNORECASE)

DEFAULT_TABLE = "machine_activity"


def extract_table_from_text(text_raw: str) -> str:
    t = strip_accents(text_raw).lower()
    m = TABLE_IN_TEXT_PAT.search(t)
    if m:
        return m.group(2)
    return DEFAULT_TABLE


# -------------------------
# SQL helpers
# -------------------------
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
        return {"ok": False, "error": f"psycopg2 no disponible: {PSYCOPG2_ERR}"}

    ok, reason = is_readonly(sql)
    if not ok:
        return {"ok": False, "error": reason}

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
        return {"ok": True, "rows": rows[:limit_fetch], "row_count": len(rows)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def format_rows(rows: List[Dict[str, Any]], max_rows: int = 20, max_colw: int = 40) -> str:
    if not rows:
        return "Sin filas devueltas."
    rows = rows[:max_rows]
    cols = list(rows[0].keys())

    w = {c: min(max(len(c), 8), max_colw) for c in cols}
    for r in rows:
        for c in cols:
            w[c] = min(max(w[c], len(str(r.get(c, "")))), max_colw)

    def clip(v: Any, width: int) -> str:
        s = str(v)
        return s if len(s) <= width else s[: width - 1] + "…"

    header = " | ".join(c.ljust(w[c]) for c in cols)
    sep = "-+-".join("-" * w[c] for c in cols)
    body = []
    for r in rows:
        body.append(" | ".join(clip(r.get(c, ""), w[c]).ljust(w[c]) for c in cols))
    return header + "\n" + sep + "\n" + "\n".join(body)


# -------------------------
# LLM (Ollama) NL->SQL
# -------------------------
def ollama_sql_from_nl(question: str) -> Dict[str, Any]:
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_SQL_PROMPT.strip()},
                {"role": "user", "content": question.strip()},
            ],
            "stream": False,
            "options": {"temperature": 0.0},
        }
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=30)
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


# -------------------------
# Mensajería principal
# -------------------------
def build_message(user_text: str) -> str:
    t = (user_text or "").strip()
    low = strip_accents(t).lower().strip()

    if low in {"help", "ayuda"}:
        return (
            "Comandos:\n"
            "- `help`\n"
            "- `ping`\n"
            "- `tablas`\n"
            "- `sql: <SELECT/WITH ...>`\n"
            "- `nl: <pregunta en español>`\n\n"
            "Ejemplos:\n"
            "- `nl: cuántas filas hay en machine_activity`\n"
            "- `nl: muéstrame 10 filas de time_record`\n"
            "- `sql: SELECT datname FROM pg_database LIMIT 10;`\n"
        )

    if low in {"ping", "test", "test db"}:
        r = run_sql("SELECT 1 AS ok;", limit_fetch=1)
        return "✅ DB OK (SELECT 1)" if r.get("ok") else f"❌ {r.get('error')}"

    if low in {"tablas", "tables"}:
        sql = "SELECT table_name FROM information_schema.tables WHERE table_schema='public' LIMIT 40;"
        r = run_sql(sql, limit_fetch=40)
        if not r.get("ok"):
            return f"❌ Error listando tablas: {r.get('error')}"
        tables = [f"- {x['table_name']}" for x in r.get("rows", []) if "table_name" in x]
        return "📚 Tablas (primeras 40):\n" + "\n".join(tables)

    # Manual SQL
    if low.startswith("sql:"):
        raw_sql = t.split(":", 1)[1].strip()
        if not raw_sql:
            return "❌ Usa: `sql: SELECT ...`"
        safe_sql = normalize_limit(raw_sql)
        r = run_sql(safe_sql, limit_fetch=MAX_LIMIT)
        if not r.get("ok"):
            return f"❌ {r.get('error')}\n\nSQL:\n{safe_sql}"
        table = format_rows(r.get("rows", []), max_rows=20)
        out = (
            "✅ SQL ejecutado (manual)\n\n"
            f"SQL:\n{safe_sql}\n\n"
            f"Filas devueltas: {min(len(r.get('rows', [])), MAX_LIMIT)} (total reportado: {r.get('row_count','?')})\n\n"
            f"```text\n{table}\n```"
        )
        return clip_out(out)

    # NL→SQL
    if low.startswith("nl:"):
        question = t.split(":", 1)[1].strip()
        if not question:
            return "❌ Usa: `nl: <pregunta en español>`"

        # ---- Regla determinista: "cuántas filas hay en <tabla>"
        qlow = strip_accents(question).lower()
        if COUNT_ROWS_PAT.search(qlow):
            table = extract_table_from_text(question)
            safe_sql = f"SELECT COUNT(*) AS n FROM public.{table};"
            r = run_sql(safe_sql, limit_fetch=MAX_LIMIT)
            if not r.get("ok"):
                return f"❌ Error ejecutando SQL: {r.get('error')}\n\nSQL:\n{safe_sql}"
            rows = r.get("rows", [])
            n = None
            if rows and isinstance(rows[0], dict):
                n = rows[0].get("n")
            return (
                "✅ Consulta NL (regla determinista)\n\n"
                f"Pregunta:\n{question}\n\n"
                f"SQL:\n{safe_sql}\n\n"
                f"n = {n if n is not None else '—'}"
            )

        # ---- Fallback: LLM NL->SQL
        gen = ollama_sql_from_nl(question)
        if not gen.get("ok"):
            return f"❌ Error llamando a Ollama: {gen.get('error')}"

        sql = gen.get("sql", "")
        ok, reason = is_readonly(sql)
        if not ok:
            return f"❌ SQL generado no permitido: {reason}\n\nSQL generado:\n{sql}"

        safe_sql = normalize_limit(sql)
        r = run_sql(safe_sql, limit_fetch=MAX_LIMIT)
        if not r.get("ok"):
            return f"❌ Error ejecutando SQL: {r.get('error')}\n\nSQL:\n{safe_sql}"

        table_txt = format_rows(r.get("rows", []), max_rows=20)
        out = (
            "🤖 NL→SQL (Ollama) + ejecución en PostgreSQL\n\n"
            f"Pregunta:\n{question}\n\n"
            f"SQL generado:\n{safe_sql}\n\n"
            f"Filas devueltas: {min(len(r.get('rows', [])), MAX_LIMIT)} (total reportado: {r.get('row_count','?')})\n\n"
            f"```text\n{table_txt}\n```"
        )
        return clip_out(out)

    return "Escribe `help`. Para NL→SQL usa: `nl: <pregunta>`."


class Pipeline:
    id = "jp_postgres_tbda_safe"
    name = "JP - TBDA PostgreSQL (Safe, Read-Only)"

    def _wrap_nonstream(self, msg: str):
        return {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": self.id,
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": msg}, "finish_reason": "stop"}
            ],
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
        try:
            messages = body.get("messages", [])
            user_text = (messages[-1].get("content") if messages else "") or ""
            msg = build_message(user_text)

            if body.get("stream") is True:
                return self._sse_stream(msg)
            return self._wrap_nonstream(msg)

        except Exception as e:
            err = f"❌ Error interno pipeline: {type(e).__name__}: {e}"
            if body.get("stream") is True:
                return self._sse_stream(err)
            return self._wrap_nonstream(err)
