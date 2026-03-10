import re
import json
import time
import uuid
import os
import logging
import hashlib
from datetime import datetime
from typing import TypedDict, Dict, Any, Tuple, List, Optional

import requests

# ---------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------
LOG_FILE = os.getenv("PIPELINE_LOG_FILE", "/tmp/pipeline_debug.log")

_file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

_root = logging.getLogger("jp_agent_unificado_cot_multi_db")
_root.setLevel(logging.DEBUG)
_root.addHandler(_file_handler)
# También a stderr para que OpenWebUI lo capture si está disponible
_root.addHandler(logging.StreamHandler())

logger = _root

logger.info(f"[INIT] Pipeline cargado. Log en: {LOG_FILE}")

# Intentar structlog por encima si está disponible (opcional)
try:
    import structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logger = structlog.get_logger()
except Exception:
    pass  # Seguimos con el logger estándar ya configurado

# ---------------------------------------------------------------------
# Config (ENV)
# ---------------------------------------------------------------------
PG_HOST = os.getenv("PG_HOST", "138.100.82.184")
PG_PORT = int(os.getenv("PG_PORT", "2345"))
PG_USER = os.getenv("PG_USER", "lectura")
PG_PASS = os.getenv("PG_PASS", "")
PG_TIMEOUT = int(os.getenv("PG_TIMEOUT", "8"))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://172.17.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:latest")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))
OLLAMA_MAX_RETRIES = int(os.getenv("OLLAMA_MAX_RETRIES", "3"))

DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "50"))
MAX_LIMIT = int(os.getenv("MAX_LIMIT", "200"))
MAX_CHARS_OUT = int(os.getenv("MAX_CHARS_OUT", "12000"))
MAX_METRICS = int(os.getenv("MAX_METRICS", "1000"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# ---------------------------------------------------------------------
# Dependencias opcionales
# ---------------------------------------------------------------------
try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_OK = True
    PSYCOPG2_ERR = ""
except Exception as e:
    psycopg2 = None
    PSYCOPG2_OK = False
    PSYCOPG2_ERR = str(e)

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_OK = True
    LANGGRAPH_ERR = ""
except Exception as e:
    LANGGRAPH_OK = False
    LANGGRAPH_ERR = str(e)

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|call|execute|do)\b",
    re.IGNORECASE,
)
HAS_LIMIT = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)

STOPWORDS_ES = {
    "dime", "dar", "dame", "informacion", "información", "dentro", "sobre",
    "de", "del", "la", "el", "los", "las", "un", "una", "en", "que", "qué",
    "cual", "cuál", "muestra", "muéstrame", "ver", "datos", "dato", "tabla",
    "tablas", "registro", "registros", "columnas", "columna", "campos", "campo",
    "todo", "toda", "todos", "todas", "hay", "existe", "existen", "quiero",
    "necesito", "mostrar", "muestrame", "lista", "listar"
}

GENERIC_FOCUS_TERMS = {
    "registro", "registros", "tabla", "tablas", "dato", "datos",
    "informacion", "información", "campo", "campos", "columna", "columnas"
}

def clip_out(text: str) -> str:
    if len(text) <= MAX_CHARS_OUT:
        return text
    return text[:MAX_CHARS_OUT] + "\n…(salida recortada)…"

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
    low = s.lower()
    if "information_schema" in low or "pg_catalog" in low or "pg_tables" in low or "pg_views" in low:
        return s + ";"
    if HAS_LIMIT.search(s):
        s = re.sub(
            r"\blimit\s+(\d+)\b",
            lambda m: f"LIMIT {min(int(m.group(1)), MAX_LIMIT)}",
            s,
            flags=re.IGNORECASE,
        )
        return s + ";"
    return s + f" LIMIT {default_limit};"

def fmt_rows(rows: List[Dict[str, Any]], max_rows: int = 50) -> str:
    if not rows:
        return "Sin filas."
    rows = rows[:max_rows]
    cols = list(rows[0].keys())
    out = [" | ".join(cols), "-+-".join(["-" * len(c) for c in cols])]
    for r in rows:
        out.append(" | ".join(str(r.get(c, "")) for c in cols))
    return "\n".join(out)

def extract_terms(user_text: str) -> List[str]:
    low = (user_text or "").lower()
    # Captura palabras alfanuméricas (incluyendo las que empiezan por dígito, como '1245', '2207')
    tokens = re.findall(r"[a-zA-Z0-9_][a-zA-Z0-9_]{2,}", low)
    out: List[str] = []
    for t in tokens:
        if t not in STOPWORDS_ES and t not in out:
            out.append(t)
    return out[:5]

# ---------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------
class MetricsCollector:
    def __init__(self):
        self.metrics: List[Dict[str, Any]] = []
        self.total = 0

    def record(self, component: str, duration_s: float, success: bool, metadata: Optional[Dict[str, Any]] = None):
        m = {
            "ts": datetime.utcnow().isoformat(),
            "component": component,
            "duration_ms": round(duration_s * 1000, 2),
            "success": bool(success),
            "metadata": metadata or {},
        }
        self.metrics.append(m)
        self.total += 1
        if len(self.metrics) > MAX_METRICS:
            self.metrics = self.metrics[-MAX_METRICS:]

metrics = MetricsCollector()

# ---------------------------------------------------------------------
# BBDD disponibles
# ---------------------------------------------------------------------
DB_NAMES = [
    "postgres",
    "trombofilia",
    "1245",
    "ncorrea",
    "2207",
    "autosurveillance",
    "deepquality",
    "enel",
    "enel_guillena",
    "enel_lleida",
    "jom",
    "mapvision",
    "oproject-bin",
    "template0",
    "template1",
]

DB_DESCRIPTIONS = {
    "postgres": "Base de datos principal del sistema PostgreSQL",
    "trombofilia": "Datos relacionados con estudios de trombofilia",
    "ncorrea": "Base de datos principal de ncorrea (por defecto)",
    "1245": "Base de datos del proyecto 1245",
    "2207": "Base de datos del proyecto 2207",
    "enel": "Datos de Enel",
    "enel_guillena": "Datos específicos de Enel Guillena",
    "enel_lleida": "Datos específicos de Enel Lleida",
    "jom": "Base de datos JOM",
    "mapvision": "Datos de MapVision",
    "deepquality": "Sistema de control de calidad",
    "autosurveillance": "Sistema de auto-vigilancia",
}

def db_to_route(dbname: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", dbname)
    return f"pg_{safe}"

DEFAULT_ROUTE = db_to_route("ncorrea")
available_dbs = ", ".join(DB_NAMES)

CONVERSATION_CONTEXT: Dict[str, str] = {}

def get_db_info_text() -> str:
    lines = ["📊 **Bases de datos disponibles:**\n"]
    for db in DB_NAMES:
        desc = DB_DESCRIPTIONS.get(db, "")
        if desc:
            lines.append(f"• **{db}**: {desc}")
        else:
            lines.append(f"• **{db}**")
    lines.append("\n💡 **Base de datos por defecto:** ncorrea")
    return "\n".join(lines)

# ---------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------
SUPERVISOR_PROMPT = """Eres un supervisor que decide QUÉ agente PostgreSQL debe usar el sistema y QUÉ acción debe ejecutar.

Bases disponibles:
__AVAILABLE_DBS__

Base por defecto: ncorrea
Contexto conversacional de BD: __CONTEXT_NOTE__

Devuelve SOLO un JSON válido.

Formato 1 (Consulta SQL):
{"route":"pg_ncorrea","action":"query","sql":"SELECT ..."}

Formato 2 (Respuesta directa):
{"route":"direct","action":"answer","answer":"texto"}

**REGLA CRÍTICA - CONSULTAS DIRECTAS:**
Si el usuario menciona "registros", "datos", "filas", "muestra", "dame" + [nombre_tabla]:
→ USA: SELECT * FROM [tabla] LIMIT N
→ NO USES: SELECT table_name FROM information_schema... (eso solo busca nombres)

**EJEMPLOS IMPORTANTES:**

Usuario: "registros de time_record"
→ {"route":"pg_ncorrea","action":"query","sql":"SELECT * FROM time_record LIMIT 10"}
→ NO: SELECT table_name FROM information_schema.tables WHERE table_name ILIKE '%time_record%'

Usuario: "muestra v_coils"
→ {"route":"pg_ncorrea","action":"query","sql":"SELECT * FROM v_coils LIMIT 10"}

Usuario: "10 datos de machine_activity"
→ {"route":"pg_ncorrea","action":"query","sql":"SELECT * FROM machine_activity LIMIT 10"}

Usuario: "¿qué tablas hay?"
→ {"route":"pg_ncorrea","action":"query","sql":"SELECT table_name FROM information_schema.tables WHERE table_schema='public'"}

Usuario: "columnas de time_record"
→ {"route":"pg_ncorrea","action":"query","sql":"SELECT column_name FROM information_schema.columns WHERE table_name='time_record'"}

**REGLAS:**
- Solo SELECT o WITH
- Si no se especifica BD, usa pg_ncorrea
- Si el usuario menciona una BD explícita, usa su route correspondiente
- PREFIERE consultas directas (SELECT * FROM tabla) sobre búsquedas (information_schema)
- Solo usa information_schema cuando pidan específicamente "tablas" o "columnas"
- No inventes tablas ni columnas
- Nunca devuelvas pg_direct

Usuario:
__USER_TEXT__

JSON:
"""

COT_STRATEGIES_PROMPT = """Eres un planificador SQL para PostgreSQL.

Debes devolver SOLO JSON válido con exactamente 3 estrategias.

Formato:
{
  "strategies": [
    {
      "id": 1,
      "name": "Exploración segura",
      "confidence": 90,
      "route": "pg_ncorrea",
      "sql": "SELECT ...",
      "reasoning": "..."
    },
    {
      "id": 2,
      "name": "Consulta directa",
      "confidence": 75,
      "route": "pg_ncorrea",
      "sql": "SELECT ...",
      "reasoning": "..."
    },
    {
      "id": 3,
      "name": "Búsqueda alternativa",
      "confidence": 60,
      "route": "pg_ncorrea",
      "sql": "SELECT ...",
      "reasoning": "..."
    }
  ]
}

Reglas:
- Solo SELECT o WITH
- No inventes tablas ni columnas
- Si la consulta es ambigua, prioriza information_schema
- Bases disponibles: __AVAILABLE_DBS__
- Ruta sugerida base: __BASE_ROUTE__

Usuario:
__USER_TEXT__

JSON:
"""

VALIDATION_PROMPT = """Eres un validador de resultados SQL.

Devuelve SOLO JSON válido:
{
  "is_valid": true,
  "confidence": 0.85,
  "reasoning": "..."
}

Pregunta:
__USER_TEXT__

Estrategia:
__STRATEGY_NAME__

SQL:
__SQL__

Número de filas:
__ROW_COUNT__

Primera fila:
__FIRST_ROW__
"""

ALTERNATIVE_PROMPT = """La consulta SQL anterior no produjo un resultado útil.

Pregunta original:
__USER_TEXT__

Ruta actual:
__ROUTE__

SQL fallido:
__FAILED_SQL__

Error o motivo:
__ERROR__

Devuelve SOLO un JSON válido:
{"route":"pg_ncorrea","action":"query","sql":"SELECT ..."}

Reglas:
- Solo SELECT o WITH
- No inventes tablas ni columnas
- Si falla una tabla o columna, usa information_schema
- Mantén la misma BD salvo razón clara para cambiar
"""

# ---------------------------------------------------------------------
# HTTP / LLM
# ---------------------------------------------------------------------
def _post_json(url: str, payload: Dict[str, Any], timeout: int) -> Tuple[bool, str]:
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}: {r.text[:300]}"
        return True, r.text
    except Exception as e:
        return False, str(e)

def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    t = text.strip()

    if "```json" in t:
        t = t.split("```json", 1)[1]
        if "```" in t:
            t = t.split("```", 1)[0]
    elif "```" in t:
        parts = t.split("```")
        for part in parts:
            if "{" in part and "}" in part:
                t = part
                break

    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        t = t[start:end + 1]

    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return None

def call_ollama(prompt: str, temperature: float = 0.1) -> Optional[str]:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "top_p": 0.9, "num_ctx": 4096},
    }
    ok, resp_text = _post_json(f"{OLLAMA_URL}/api/generate", payload, OLLAMA_TIMEOUT)
    if not ok:
        return None
    try:
        jresp = json.loads(resp_text)
        return jresp.get("response", "")
    except Exception:
        return None

# ---------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------
def detect_db_command(user_text: str) -> Optional[str]:
    """
    Detecta comandos de cambio de BD de forma robusta.
    Soporta: 'usa X', 've a X', 'cambia a X', 'sal de Y y ve a X'
    """
    if not user_text:
        return None
    
    low = user_text.lower().strip()
    
    # Patrones en orden de especificidad
    patterns = [
        # "sal de X y ve a Y"
        r"sal(?:ir)?\s+de\s+\w+\s+(?:y\s+)?(?:ve|ir|usa|usar|cambia|cambiar)\s+a\s+(\w+)",
        
        # "usa/cambia/ve/ir/conecta(te) + a + [nombre]"
        r"(?:usa|usar|cambia|cambiar|ve|ir|vete|anda|conecta|conectate|conectá|conectáte)\s+a\s+(?:la\s+)?(?:bd\s+|base\s+)?(?:de\s+)?(\w+)",
        
        # "usa/usar + [nombre]" (sin "a")
        r"(?:usa|usar)\s+(\w+)(?:\s|$)",
        
        # "base de datos [nombre]"
        r"base\s+de\s+datos\s+(\w+)",
        
        # "la bd [nombre]"
        r"la\s+bd\s+(\w+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, low)
        if match:
            candidate = match.group(1).strip()
            
            # Verificar que sea BD válida
            for db in DB_NAMES:
                if db.lower() == candidate.lower():
                    if DEBUG_MODE:
                        logger.info(f"[BD Detectada] '{candidate}' → {db}")
                    return db
    
    return None


def extract_db_from_history(messages: list) -> Optional[str]:
    """
    Lee el historial de mensajes buscando el último cambio de BD confirmado.
    Busca tanto en mensajes del usuario (comandos) como del asistente (confirmaciones).
    Esto evita depender de CONVERSATION_CONTEXT en memoria, que no sobrevive
    entre workers distintos de OpenWebUI.
    """
    # Recorrer mensajes de más reciente a más antiguo (excluir el último, que es el actual)
    for msg in reversed(messages[:-1]):
        role = msg.get("role", "")
        text = (msg.get("content") or "").lower().strip()

        if role == "assistant":
            # Buscar confirmaciones del asistente tipo "Contexto cambiado a: enel"
            m = re.search(r"contexto cambiado a[:\s]+([a-zA-Z0-9_\-]+)", text)
            if m:
                candidate = m.group(1).strip()
                for db in DB_NAMES:
                    if db.lower() == candidate.lower():
                        return db

        if role == "user":
            # Buscar comandos de cambio de BD en mensajes anteriores del usuario
            detected = detect_db_command(text)
            if detected:
                return detected

    return None

def infer_route_from_text(user_text: str, conversation_id: str = "default") -> str:
    context_db = CONVERSATION_CONTEXT.get(conversation_id)
    if context_db in DB_NAMES:
        return db_to_route(context_db)

    low = (user_text or "").lower()

    for db in DB_NAMES:
        if db.lower() in low:
            return db_to_route(db)

    trombo_terms = {
        "trombofilia", "pacientes", "pacientes_ok", "tratamiento", "tratamientos",
        "diagnostico", "diagnóstico", "medicacion", "medicación", "terapia",
    }
    if any(term in low for term in trombo_terms):
        return db_to_route("trombofilia")

    return DEFAULT_ROUTE

def normalize_table_name(table_candidate: str, route: str, conversation_id: str = "default") -> str:
    """
    Normaliza el nombre de tabla buscando en information_schema.
    Si el usuario dice 'v_coils' pero la tabla es 'V_Coils', devuelve 'V_Coils'.
    """
    # Extraer nombre de BD de la ruta
    db_name = route.replace("pg_", "").replace("_", "-") if route.startswith("pg_") else "ncorrea"
    
    # Buscar en DB_NAMES el nombre real
    db_name_real = None
    for db in DB_NAMES:
        if db.lower() == db_name.lower() or db.replace("-", "_").lower() == db_name.lower():
            db_name_real = db
            break
    
    if not db_name_real:
        db_name_real = "ncorrea"
    
    agent = AGENTS.get(db_to_route(db_name_real))
    if not agent:
        return table_candidate  # No podemos buscar, usar como está
    
    # Buscar tabla con nombre similar (case-insensitive) — pg_tables es visible sin USAGE
    search_sql = f"""
        SELECT tablename AS table_name
        FROM pg_tables
        WHERE schemaname = 'public'
        AND LOWER(tablename) = LOWER('{table_candidate}')
        LIMIT 1
    """
    
    try:
        result = agent.run(search_sql)
        if result.get("ok") and result.get("rows"):
            real_name = result["rows"][0].get("table_name")
            if real_name:
                if DEBUG_MODE:
                    logger.info(f"[Normalize] '{table_candidate}' → '{real_name}'")
                return real_name
    except Exception as e:
        if DEBUG_MODE:
            logger.info(f"[Normalize] Error buscando tabla: {e}")
    
    # Si no encontramos, devolver el original
    return table_candidate

def heuristic_plan(user_text: str, conversation_id: str = "default") -> Optional[Dict[str, Any]]:
    logger.info(f"[HEURISTIC_PLAN INICIADO] Input: '{user_text}'")
    
    low = (user_text or "").lower().strip()
    original = (user_text or "").strip()  # Preservar mayúsculas
    route = infer_route_from_text(user_text, conversation_id)
    
    logger.info(f"[HEURISTIC_PLAN] Low: '{low}' | Route inferido: '{route}'")
    
    # ============================================================================
    # PATRÓN PRIORITARIO: "tablas de [BD]" - DEBE IR PRIMERO
    # ============================================================================
    # Ej: "tablas de 1245", "muéstrame las tablas de enel", "tablas de deepquality"
    m_db = re.search(r"(?:tablas|tabla)\s+(?:de|del|en)\s+([a-zA-Z0-9_\-]+)", low)
    
    logger.info(f"[PATRÓN TABLAS DE BD] Match: {m_db}")
    
    if m_db:
        db_candidate = m_db.group(1)
        logger.info(f"[PATRÓN TABLAS DE BD] Detectado candidato: '{db_candidate}'")
        
        # Verificar que sea una BD válida
        target_db = None
        for db in DB_NAMES:
            if db.lower() == db_candidate.lower() or db.replace("-", "").lower() == db_candidate.replace("-", "").lower():
                target_db = db
                logger.info(f"[PATRÓN TABLAS DE BD] ✅ Match con DB: '{db}'")
                break
        
        if target_db:
            # Cambiar contexto a esa BD
            CONVERSATION_CONTEXT[conversation_id] = target_db
            route = db_to_route(target_db)
            logger.info(f"[PATRÓN TABLAS DE BD] Route asignado: '{route}'")
            
            # Buscar solo en schemas accesibles (excluir sistema y timescaledb)
            sql = "SELECT schemaname AS table_schema, tablename AS table_name FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') AND schemaname NOT LIKE 'pg_%' AND schemaname NOT LIKE '_timescaledb%' ORDER BY schemaname, tablename"
            
            logger.info(f"[PATRÓN TABLAS DE BD] ✅ Retornando resultado para BD: '{target_db}'")
            return {
                "route": route,
                "action": "query",
                "sql": sql,
                "source": "heuristic",
            }
        else:
            logger.warning(f"[PATRÓN TABLAS DE BD] ❌ '{db_candidate}' no encontrado en DB_NAMES: {DB_NAMES}")
    else:
        logger.info(f"[PATRÓN TABLAS DE BD] ❌ Patrón no detectó match en: '{low}'")
    
    # ============================================================================
    # OTROS PATRONES
    # ============================================================================

    # PATRÓN 1: "N registros de tabla"
    # Ej: "10 registros de time_record", "50 registros de V_Coils"
    m_low = re.search(r"(\d+)\s+registros?\s+(?:de|del|en)?\s*(?:la\s+)?(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", low)
    if m_low:
        n = int(m_low.group(1))
        # Extraer tabla del texto ORIGINAL para preservar mayúsculas
        m_orig = re.search(r"(\d+)\s+registros?\s+(?:de|del|en)?\s*(?:la\s+)?(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", original, re.IGNORECASE)
        table_candidate = m_orig.group(2) if m_orig else m_low.group(2)
        
        # Normalizar nombre (busca el nombre real en information_schema)
        table = normalize_table_name(table_candidate, route, conversation_id)
        
        n = max(1, min(n, MAX_LIMIT))
        sql = f'SELECT * FROM "{table}" LIMIT {n}'  # Entre comillas para preservar case
        if DEBUG_MODE:
            logger.info(f"[Heuristic] ✅ Patrón 1 detectado: {n} registros de '{table}' (input: '{table_candidate}')")
            logger.info(f"[Heuristic] SQL: {sql}")
        return {
            "route": route,
            "action": "query",
            "sql": sql,
            "source": "heuristic",
        }

    # PATRÓN 2: "registros/datos/filas + de + tabla"
    # Ej: "registros de time_record", "datos de V_Coils", "filas de machine_activity"
    m_low = re.search(r"(?:registros?|datos?|filas?|información|informacion)\s+(?:de|del|en)\s+(?:la\s+)?(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", low)
    if m_low:
        # Extraer del original para preservar mayúsculas
        m_orig = re.search(r"(?:registros?|datos?|filas?|información|informacion)\s+(?:de|del|en)\s+(?:la\s+)?(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", original, re.IGNORECASE)
        table_candidate = m_orig.group(1) if m_orig else m_low.group(1)
        
        # Normalizar nombre
        table = normalize_table_name(table_candidate, route, conversation_id)
        
        n_match = re.search(r"(\d+)", low)
        n = int(n_match.group(1)) if n_match else 10
        n = max(1, min(n, MAX_LIMIT))
        sql = f'SELECT * FROM "{table}" LIMIT {n}'
        if DEBUG_MODE:
            logger.info(f"[Heuristic] ✅ Patrón 2 detectado: registros/datos de '{table}' (input: '{table_candidate}')")
            logger.info(f"[Heuristic] SQL: {sql}")
        return {
            "route": route,
            "action": "query",
            "sql": sql,
            "source": "heuristic",
        }

    # PATRÓN 3: "muestra/dame/ver + tabla"
    # Ej: "muestra time_record", "dame V_Coils", "ver machine_activity"
    m_low = re.search(r"(?:muestra|muestrame|muéstrame|dame|ver|visualiza)\s+(?:la\s+)?(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", low)
    if m_low:
        # Extraer del original
        m_orig = re.search(r"(?:muestra|muestrame|muéstrame|dame|ver|visualiza)\s+(?:la\s+)?(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", original, re.IGNORECASE)
        table = m_orig.group(1) if m_orig else m_low.group(1)
        # Evitar palabras comunes que no son tablas
        if table.lower() not in ["las", "los", "una", "el", "de", "que", "qué"]:
            n_match = re.search(r"(\d+)", low)
            n = int(n_match.group(1)) if n_match else 10
            n = max(1, min(n, MAX_LIMIT))
            sql = f'SELECT * FROM "{table}" LIMIT {n}'
            if DEBUG_MODE:
                logger.info(f"[Heuristic] ✅ Patrón 3 detectado: muestra/dame '{table}'")
                logger.info(f"[Heuristic] SQL: {sql}")
            return {
                "route": route,
                "action": "query",
                "sql": sql,
                "source": "heuristic",
            }

    # PATRÓN 4: "tabla + tabla_nombre" (para capturar "tabla time_record")
    m_low = re.search(r"(?:tabla)\s+([a-zA-Z_][a-zA-Z0-9_]*)", low)
    if m_low and any(x in low for x in ["registro", "registros", "datos", "información", "informacion", "muestra", "dame", "ver"]):
        m_orig = re.search(r"(?:tabla)\s+([a-zA-Z_][a-zA-Z0-9_]*)", original, re.IGNORECASE)
        table = m_orig.group(1) if m_orig else m_low.group(1)
        n_match = re.search(r"(\d+)\s+registros?", low)
        n = int(n_match.group(1)) if n_match else 10
        n = max(1, min(n, MAX_LIMIT))
        sql = f'SELECT * FROM "{table}" LIMIT {n}'
        if DEBUG_MODE:
            logger.info(f"[Heuristic] ✅ Patrón 4 detectado: tabla '{table}'")
            logger.info(f"[Heuristic] SQL: {sql}")
        return {
            "route": route,
            "action": "query",
            "sql": sql,
            "source": "heuristic",
        }

    # PATRÓN 5: "columnas de tabla"
    m_low = re.search(r"(?:columnas|campos)\s+(?:de|del|de la)?\s*(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", low)
    if m_low:
        m_orig = re.search(r"(?:columnas|campos)\s+(?:de|del|de la)?\s*(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", original, re.IGNORECASE)
        table = m_orig.group(1) if m_orig else m_low.group(1)
        sql = f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}' ORDER BY ordinal_position"
        if DEBUG_MODE:
            logger.info(f"[Heuristic] ✅ Patrón 5 detectado: columnas de '{table}'")
        return {
            "route": route,
            "action": "query",
            "sql": sql,
            "source": "heuristic",
        }

    # PATRÓN 6: "tablas" (listar todas)
    if re.search(r"(?:tablas|listar tablas|muestrame las tablas|muéstrame las tablas)", low):
        # Buscar solo en schemas accesibles (excluir sistema y timescaledb)
        sql = "SELECT schemaname AS table_schema, tablename AS table_name FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') AND schemaname NOT LIKE 'pg_%' AND schemaname NOT LIKE '_timescaledb%' ORDER BY schemaname, tablename"
        if DEBUG_MODE:
            logger.info(f"[Heuristic] ✅ Patrón 6 detectado: listar tablas")
        return {
            "route": route,
            "action": "query",
            "sql": sql,
            "source": "heuristic",
        }

    # Patrones adicionales al final
    m_low = re.search(r"registros?\s+(?:de|del)?\s*(?:la\s+)?(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", low)
    if m_low:
        m_orig = re.search(r"registros?\s+(?:de|del)?\s*(?:la\s+)?(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", original, re.IGNORECASE)
        table = m_orig.group(1) if m_orig else m_low.group(1)
        sql = f'SELECT * FROM "{table}" LIMIT 10'
        if DEBUG_MODE:
            logger.info(f"[Heuristic] ✅ Patrón extra 1: registros de '{table}'")
        return {
            "route": route,
            "action": "query",
            "sql": sql,
            "source": "heuristic",
        }

    m_low = re.search(r"(?:datos|información|informacion)\s+(?:de|del)?\s*(?:la\s+)?(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", low)
    if m_low:
        m_orig = re.search(r"(?:datos|información|informacion)\s+(?:de|del)?\s*(?:la\s+)?(?:tabla\s+)?([a-zA-Z_][a-zA-Z0-9_]*)", original, re.IGNORECASE)
        table = m_orig.group(1) if m_orig else m_low.group(1)
        sql = f'SELECT * FROM "{table}" LIMIT 10'
        if DEBUG_MODE:
            logger.info(f"[Heuristic] ✅ Patrón extra 2: datos de '{table}'")
        return {
            "route": route,
            "action": "query",
            "sql": sql,
            "source": "heuristic",
        }

    logger.info("[HEURISTIC_PLAN] ❌ Ningún patrón detectado, pasando a LLM")
    
    return None

# ---------------------------------------------------------------------
# Supervisor / CoT
# ---------------------------------------------------------------------
def supervisor_plan(user_text: str, conversation_id: str = "default", context_note: str = "") -> Dict[str, Any]:
    start = time.time()

    user_lower = user_text.lower().strip()
    if any(p in user_lower for p in ["qué bases", "cuáles bases", "bases disponibles", "listar bases", "mostrar bases", "bases de datos disponibles"]):
        return {"route": "direct", "action": "answer", "answer": get_db_info_text(), "source": "direct"}

    target_db = detect_db_command(user_text)
    if target_db:
        CONVERSATION_CONTEXT[conversation_id] = target_db
        
        # Mensaje mejorado
        desc = DB_DESCRIPTIONS.get(target_db, "")
        msg = f"✅ **Contexto cambiado a: {target_db}**\n\n"
        if desc:
            msg += f"📋 {desc}\n\n"
        msg += f"Ahora todas tus consultas usarán la base **{target_db}**.\n\n"
        msg += "💡 Ejemplos:\n"
        if target_db == "trombofilia":
            msg += "• 'muéstrame 10 registros de pacientes'\n"
            msg += "• 'columnas de tratamiento'\n"
        else:
            msg += "• 'muéstrame las tablas'\n"
            msg += "• 'registros de [tabla]'\n"
        msg += "\n_Para cambiar: 'usa [otra_bd]'_"
        
        return {
            "route": "direct",
            "action": "answer",
            "answer": msg,
            "source": "direct",
        }

    heur = heuristic_plan(user_text, conversation_id)
    if heur:
        metrics.record("supervisor_heuristic", time.time() - start, True)
        return heur

    fallback_route = infer_route_from_text(user_text, conversation_id)
    fallback = {
        "route": fallback_route,
        "action": "query",
        "sql": "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name",
        "source": "fallback",
    }

    prompt = (
        SUPERVISOR_PROMPT
        .replace("__AVAILABLE_DBS__", available_dbs)
        .replace("__CONTEXT_NOTE__", context_note)
        .replace("__USER_TEXT__", user_text)
    )

    for _ in range(OLLAMA_MAX_RETRIES):
        response = call_ollama(prompt, 0.15)
        if not response:
            continue
        extracted = extract_json_object(response)
        if extracted and "route" in extracted:
            if extracted.get("route") == "pg_direct":
                extracted["route"] = "direct"
            if extracted.get("route") == "direct" and "answer" not in extracted:
                extracted["answer"] = "No pude entender la consulta con suficiente precisión. ¿Puedes reformularla?"
            if not extracted.get("route"):
                extracted["route"] = fallback_route
            extracted["source"] = extracted.get("source", "llm")
            metrics.record("supervisor", time.time() - start, True)
            return extracted

    metrics.record("supervisor", time.time() - start, False)
    return fallback

def generate_cot_strategies(user_text: str, conversation_id: str = "default") -> List[Dict[str, Any]]:
    base_route = infer_route_from_text(user_text, conversation_id)

    prompt = (
        COT_STRATEGIES_PROMPT
        .replace("__AVAILABLE_DBS__", available_dbs)
        .replace("__BASE_ROUTE__", base_route)
        .replace("__USER_TEXT__", user_text)
    )

    for _ in range(OLLAMA_MAX_RETRIES):
        response = call_ollama(prompt, 0.2)
        if not response:
            continue
        parsed = extract_json_object(response)
        if parsed and isinstance(parsed.get("strategies"), list):
            valid: List[Dict[str, Any]] = []
            for s in parsed["strategies"]:
                if not isinstance(s, dict):
                    continue
                if not s.get("sql"):
                    continue
                valid.append(
                    {
                        "id": s.get("id", 0),
                        "name": str(s.get("name", "Sin nombre"))[:80],
                        "confidence": int(s.get("confidence", 50)),
                        "route": s.get("route", base_route),
                        "sql": str(s.get("sql", "")).strip(),
                        "reasoning": str(s.get("reasoning", ""))[:300],
                    }
                )
            if valid:
                valid.sort(key=lambda x: x.get("confidence", 0), reverse=True)
                return valid[:3]

    heur = heuristic_plan(user_text, conversation_id)
    terms = extract_terms(user_text)
    fallback: List[Dict[str, Any]] = []

    if heur:
        fallback.append(
            {
                "id": 1,
                "name": "Heurística directa",
                "confidence": 95,
                "route": heur["route"],
                "sql": heur["sql"],
                "reasoning": "Patrón claro detectado en la petición del usuario",
            }
        )

    if terms:
        safe = terms[0].replace("'", "''")
        fallback.append(
            {
                "id": 2,
                "name": "Buscar tablas",
                "confidence": 60,
                "route": base_route,
                "sql": f"SELECT table_schema, table_name FROM information_schema.tables WHERE table_name ILIKE '%{safe}%' ORDER BY table_schema, table_name",
                "reasoning": "Exploración de tablas por término",
            }
        )
        fallback.append(
            {
                "id": 3,
                "name": "Buscar columnas",
                "confidence": 55,
                "route": base_route,
                "sql": f"SELECT table_schema, table_name, column_name FROM information_schema.columns WHERE column_name ILIKE '%{safe}%' ORDER BY table_schema, table_name, ordinal_position",
                "reasoning": "Exploración de columnas por término",
            }
        )

    if not fallback:
        fallback.append(
            {
                "id": 1,
                "name": "Listar tablas públicas",
                "confidence": 50,
                "route": base_route,
                "sql": "SELECT schemaname AS table_schema, tablename AS table_name FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') AND schemaname NOT LIKE 'pg_%' AND schemaname NOT LIKE '_timescaledb%' ORDER BY schemaname, tablename",
                "reasoning": "Fallback general",
            }
        )

    return fallback[:3]

def validate_result(user_text: str, strategy_name: str, sql: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    low = (user_text or "").lower()

    if not rows:
        return {"is_valid": False, "confidence": 0.2, "reasoning": "La consulta no devolvió filas"}

    if any(
        x in low for x in [
            "registro", "registros", "datos de la tabla", "información de la tabla",
            "informacion de la tabla", "registros de la tabla", "registros del", "registros de",
        ]
    ):
        return {
            "is_valid": True,
            "confidence": 0.95,
            "reasoning": "El usuario pidió registros y la consulta devolvió filas",
        }

    prompt = (
        VALIDATION_PROMPT
        .replace("__USER_TEXT__", user_text)
        .replace("__STRATEGY_NAME__", strategy_name)
        .replace("__SQL__", sql)
        .replace("__ROW_COUNT__", str(len(rows)))
        .replace("__FIRST_ROW__", str(rows[0])[:300])
    )

    response = call_ollama(prompt, 0.0)
    if response:
        parsed = extract_json_object(response)
        if parsed and "is_valid" in parsed:
            try:
                conf = float(parsed.get("confidence", 0.0))
            except Exception:
                conf = 0.0
            conf = max(0.0, min(1.0, conf))
            return {
                "is_valid": bool(parsed.get("is_valid")),
                "confidence": conf,
                "reasoning": str(parsed.get("reasoning", ""))[:300],
            }

    return {"is_valid": True, "confidence": 0.55, "reasoning": "Validación heurística: devolvió filas"}

def generate_alternative(user_text: str, failed_sql: str, error: str, route: str, conversation_id: str = "default") -> Dict[str, Any]:
    prompt = (
        ALTERNATIVE_PROMPT
        .replace("__USER_TEXT__", user_text)
        .replace("__FAILED_SQL__", failed_sql)
        .replace("__ERROR__", error)
        .replace("__ROUTE__", route)
    )

    for _ in range(2):
        response = call_ollama(prompt, 0.25)
        if not response:
            continue
        parsed = extract_json_object(response)
        if parsed and "sql" in parsed:
            parsed["source"] = "cot_alternative"
            return parsed

    terms = extract_terms(user_text)
    if terms:
        safe = terms[0].replace("'", "''")
        return {
            "route": route,
            "action": "query",
            "sql": f"SELECT table_schema, table_name FROM information_schema.tables WHERE table_name ILIKE '%{safe}%' ORDER BY table_schema, table_name",
            "source": "cot_alternative_fallback",
        }

    return {
        "route": route,
        "action": "query",
        "sql": "SELECT schemaname AS table_schema, tablename AS table_name FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema') AND schemaname NOT LIKE 'pg_%' AND schemaname NOT LIKE '_timescaledb%' ORDER BY schemaname, tablename",
        "source": "cot_alternative_fallback",
    }

# ---------------------------------------------------------------------
# Agentes Postgres por BD
# ---------------------------------------------------------------------
class PostgresSafeAgent:
    def __init__(self, route: str, dbname: str):
        self.route = route
        self.dbname = dbname

    def run(self, sql: str) -> Dict[str, Any]:
        start = time.time()

        if not PSYCOPG2_OK:
            metrics.record("postgres_query", time.time() - start, False, {"error": PSYCOPG2_ERR, "db": self.dbname})
            return {"ok": False, "error": f"psycopg2 no disponible: {PSYCOPG2_ERR}", "sql": sql, "db": self.dbname}

        ok, reason = is_readonly(sql)
        if not ok:
            metrics.record("postgres_query", time.time() - start, False, {"error": reason, "db": self.dbname})
            return {"ok": False, "error": reason, "sql": sql, "db": self.dbname}

        sql2 = normalize_limit(sql)

        try:
            conn = psycopg2.connect(
                host=PG_HOST,
                port=PG_PORT,
                dbname=self.dbname,
                user=PG_USER,
                password=PG_PASS,
                connect_timeout=PG_TIMEOUT,
            )
            conn.set_session(readonly=True, autocommit=True)

            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql2)
                try:
                    rows = cur.fetchall()
                except psycopg2.ProgrammingError:
                    rows = []

            conn.close()

            metrics.record("postgres_query", time.time() - start, True, {"rows": len(rows), "db": self.dbname})
            return {"ok": True, "rows": rows[:MAX_LIMIT], "row_count": len(rows), "sql": sql2, "db": self.dbname}

        except Exception as e:
            metrics.record("postgres_query", time.time() - start, False, {"error": str(e), "db": self.dbname})
            return {"ok": False, "error": str(e), "sql": sql2, "db": self.dbname}

AGENTS: Dict[str, PostgresSafeAgent] = {}
for db in DB_NAMES:
    AGENTS[db_to_route(db)] = PostgresSafeAgent(route=db_to_route(db), dbname=db)

def validate_plan(plan: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(plan, dict):
        return False, "plan no es dict"

    route = plan.get("route")
    action = plan.get("action")

    if route is None or action is None:
        return False, "Falta route/action"

    if route == "direct":
        if action != "answer":
            return False, "direct requiere action=answer"
        if "answer" not in plan:
            return False, "Falta answer"
        return True, "ok"

    if route not in AGENTS:
        return False, f"No conozco la base de datos '{str(route).replace('pg_', '')}'. Las disponibles son: {available_dbs}"

    if action != "query":
        return False, "Para consultas a BD se requiere action=query"

    sql = (plan.get("sql") or "").strip()
    if not sql:
        return False, "Falta la consulta SQL"

    ok, reason = is_readonly(sql)
    if not ok:
        return False, reason

    return True, "ok"

# ---------------------------------------------------------------------
# Schema discovery para aclaraciones
# ---------------------------------------------------------------------
def schema_discovery(route: str, term: str) -> Dict[str, List[Dict[str, Any]]]:
    agent = AGENTS.get(route)
    if not agent:
        return {"tables": [], "columns": []}

    safe_term = term.replace("'", "''")

    q_tables = f"""
    SELECT schemaname AS table_schema, tablename AS table_name
    FROM pg_tables
    WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
      AND tablename ILIKE '%{safe_term}%'
    ORDER BY schemaname, tablename
    LIMIT 20
    """

    q_cols = f"""
    SELECT table_schema, table_name, column_name
    FROM information_schema.columns
    WHERE column_name ILIKE '%{safe_term}%'
    ORDER BY table_schema, table_name, ordinal_position
    LIMIT 20
    """

    t_res = agent.run(q_tables)
    c_res = agent.run(q_cols)

    return {
        "tables": t_res.get("rows", []) if t_res.get("ok") else [],
        "columns": c_res.get("rows", []) if c_res.get("ok") else [],
    }

def build_clarification_question(user_text: str, route: str) -> str:
    terms = extract_terms(user_text)

    if not terms:
        return (
            "No entendí del todo la consulta.\n\n"
            "Aclárame estas dos cosas:\n"
            "1) ¿Qué tabla quieres consultar?\n"
            "2) ¿Quieres ver columnas o registros?"
        )

    focus = terms[0]
    if focus in GENERIC_FOCUS_TERMS and len(terms) > 1:
        focus = terms[1]

    disc = schema_discovery(route, focus)

    table_suggestions = [
        f"{r.get('table_schema')}.{r.get('table_name')}"
        for r in disc["tables"][:6]
        if r.get("table_schema") and r.get("table_name")
    ]

    col_suggestions = [
        f"{r.get('table_schema')}.{r.get('table_name')}.{r.get('column_name')}"
        for r in disc["columns"][:6]
        if r.get("table_schema") and r.get("table_name") and r.get("column_name")
    ]

    parts = [
        "No puedo resolver la consulta con suficiente precisión.",
        "",
        f"Término detectado: **{focus}**",
    ]

    if table_suggestions:
        parts += ["", "Tablas relacionadas encontradas:"]
        parts += [f"• {x}" for x in table_suggestions]

    if col_suggestions:
        parts += ["", "Columnas relacionadas encontradas:"]
        parts += [f"• {x}" for x in col_suggestions]

    if not table_suggestions and not col_suggestions:
        parts += ["", "No encontré coincidencias claras en el esquema."]

    parts += [
        "",
        "Aclárame qué quieres exactamente:",
        "1) columnas de una tabla concreta",
        "2) registros de una tabla concreta",
        "3) buscar un campo relacionado dentro de una tabla",
    ]

    return "\n".join(parts)

# ---------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------
class AgentState(TypedDict, total=False):
    user_text: str
    conversation_id: str
    messages_history: list
    route: str
    plan: Dict[str, Any]
    db: Dict[str, Any]
    answer: str
    retry_count: int
    use_multi_strategy: bool
    strategies: List[Dict[str, Any]]
    strategy_index: int
    needs_clarification: bool
    clarification_question: str

# ---------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------
def node_input(state: AgentState) -> AgentState:
    return state

def node_supervisor(state: AgentState) -> AgentState:
    txt = state.get("user_text", "") or ""
    conversation_id = state.get("conversation_id", "default")

    # Recuperar BD activa del historial de mensajes (robusto ante múltiples workers)
    messages_history = state.get("messages_history", []) or []
    history_db = extract_db_from_history(messages_history)
    if history_db:
        CONVERSATION_CONTEXT[conversation_id] = history_db
        logger.info(f"[Supervisor] BD recuperada del historial: '{history_db}'")

    context_db = CONVERSATION_CONTEXT.get(conversation_id)
    context_note = f"Usuario en BD: {context_db}" if context_db else "Sin contexto"

    plan = supervisor_plan(txt, conversation_id, context_note)

    if plan.get("route") is None:
        plan["route"] = DEFAULT_ROUTE

    ok, reason = validate_plan(plan)
    if not ok:
        plan = {
            "route": "direct",
            "action": "answer",
            "answer": f"🤔 {reason}\n\n¿Necesitas ayuda? Prueba con: 'muéstrame las bases de datos disponibles'",
            "source": "direct",
        }

    if plan.get("source") == "heuristic":
        use_multi = False
    else:
        low = txt.lower()
        use_multi = any(x in low for x in [
            "información", "informacion", "datos", "dentro de", "sobre",
            "registros de la tabla", "registros del", "registros de",
        ])

    return {
        "plan": plan,
        "route": plan.get("route", "direct"),
        "retry_count": 0,
        "use_multi_strategy": use_multi,
        "needs_clarification": False,
    }

def decide_after_supervisor(state: AgentState) -> str:
    plan = state.get("plan", {})
    route = plan.get("route", "direct")

    if plan.get("source") == "heuristic":
        return "postgres"

    if route == "direct":
        answer = (plan.get("answer", "") or "").lower()
        if "reformular" in answer or "no pude entender" in answer:
            return "clarify"
        return "done"

    if state.get("use_multi_strategy", False):
        return "strategies"

    return "postgres"

def node_generate_strategies(state: AgentState) -> AgentState:
    user_text = state.get("user_text", "")
    conversation_id = state.get("conversation_id", "default")
    strategies = generate_cot_strategies(user_text, conversation_id)
    if not strategies:
        return state

    first = strategies[0]
    return {
        "strategies": strategies,
        "strategy_index": 0,
        "plan": {
            "route": first.get("route", DEFAULT_ROUTE),
            "action": "query",
            "sql": first.get("sql", ""),
            "strategy_name": first.get("name", "Estrategia 1"),
            "source": "multi_strategy",
        },
        "route": first.get("route", DEFAULT_ROUTE),
    }

def node_postgres_agent(state: AgentState) -> AgentState:
    plan = state.get("plan", {}) or {}
    route = plan.get("route") or DEFAULT_ROUTE
    sql = (plan.get("sql") or "").strip()

    if route == "direct":
        return state

    agent = AGENTS.get(route)
    if not agent:
        return {"db": {"ok": False, "error": f"Ruta no soportada: {route}", "sql": sql, "db": route}}

    return {"db": agent.run(sql)}

def should_after_postgres(state: AgentState) -> str:
    plan = state.get("plan", {})
    route = plan.get("route", "direct")
    retry_count = state.get("retry_count", 0)

    if route == "direct":
        return "done"

    # Si el plan viene de heuristica, siempre ir a done sin importar filas o errores.
    # Evita que consultas directas (tablas de BD, registros de tabla) caigan a clarify.
    if plan.get("source") == "heuristic":
        return "done"

    db_result = state.get("db", {})
    if not db_result.get("ok"):
        strategies = state.get("strategies", [])
        idx = state.get("strategy_index", 0)
        if strategies and idx + 1 < len(strategies):
            return "next_strategy"
        if retry_count >= 2:
            return "clarify"
        return "alternative"

    rows = db_result.get("rows", [])
    if rows:
        if state.get("strategies"):
            strategy_name = plan.get("strategy_name", "Estrategia")
            val = validate_result(
                state.get("user_text", ""),
                strategy_name,
                db_result.get("sql", ""),
                rows,
            )
            if val.get("is_valid") and val.get("confidence", 0) >= 0.7:
                return "done"

            strategies = state.get("strategies", [])
            idx = state.get("strategy_index", 0)
            if strategies and idx + 1 < len(strategies):
                return "next_strategy"

            if retry_count >= 1:
                return "clarify"
            return "alternative"

        return "done"

    strategies = state.get("strategies", [])
    idx = state.get("strategy_index", 0)
    if strategies and idx + 1 < len(strategies):
        return "next_strategy"

    if retry_count >= 1:
        return "clarify"

    return "alternative"

def node_next_strategy(state: AgentState) -> AgentState:
    strategies = state.get("strategies", [])
    idx = state.get("strategy_index", 0) + 1

    if idx >= len(strategies):
        return state

    current = strategies[idx]
    return {
        "strategy_index": idx,
        "plan": {
            "route": current.get("route", DEFAULT_ROUTE),
            "action": "query",
            "sql": current.get("sql", ""),
            "strategy_name": current.get("name", f"Estrategia {idx + 1}"),
            "source": "multi_strategy",
        },
        "route": current.get("route", DEFAULT_ROUTE),
    }

def node_generate_alternative(state: AgentState) -> AgentState:
    user_text = state.get("user_text", "")
    db_result = state.get("db", {})
    route = state.get("route", DEFAULT_ROUTE)
    conversation_id = state.get("conversation_id", "default")
    retry_count = state.get("retry_count", 0)

    failed_sql = db_result.get("sql", "")
    error = db_result.get("error", "Sin resultados o interpretación insuficiente")

    alternative = generate_alternative(user_text, failed_sql, error, route, conversation_id)
    if not alternative.get("route"):
        alternative["route"] = route

    return {
        "plan": alternative,
        "route": alternative.get("route", route),
        "retry_count": retry_count + 1,
        "strategies": [],
        "strategy_index": 0,
    }

def node_clarify(state: AgentState) -> AgentState:
    user_text = state.get("user_text", "")
    route = state.get("route", DEFAULT_ROUTE)
    question = build_clarification_question(user_text, route)
    return {
        "needs_clarification": True,
        "clarification_question": question,
        "answer": question,
    }

def node_done(state: AgentState) -> AgentState:
    if state.get("needs_clarification"):
        return {"answer": state.get("clarification_question", "Necesito una aclaración.")}

    plan = state.get("plan", {}) or {}
    route = plan.get("route", "direct")

    if route == "direct":
        ans = plan.get("answer", "")
        if isinstance(ans, list):
            ans = "\n".join(str(x) for x in ans)
        return {"answer": ans}

    db = state.get("db", {}) or {}
    retry_count = state.get("retry_count", 0)
    strategies = state.get("strategies", [])
    strategy_name = plan.get("strategy_name", "")

    if not db.get("ok"):
        error_msg = db.get("error", "Error desconocido")
        sql_used = db.get("sql", "")
        return {"answer": f"❌ **Error en la consulta:**\n{error_msg}\n\n**SQL ejecutado:**\n```sql\n{sql_used}\n```"}

    rows = db.get("rows", []) or []
    sql_used = db.get("sql", "")
    db_name = db.get("db", "")

    if not rows:
        is_tables_query = "information_schema.tables" in (sql_used or "") or "pg_tables" in (sql_used or "")
        if is_tables_query:
            ans = (
                f"ℹ️ **No se encontraron tablas en la BD `{db_name}`**\n\n"
                f"Posibles causas:\n"
                f"• La BD no tiene tablas en schemas visibles (public, etc.)\n"
                f"• El usuario `{PG_USER}` no tiene permisos en esa BD\n"
                f"• La BD está vacía\n\n"
                f"**SQL ejecutado:**\n```sql\n{sql_used}\n```"
            )
        else:
            ans = f"ℹ️ **La consulta no devolvió resultados**\n\n**Base de datos:** {db_name}\n**SQL:**\n```sql\n{sql_used}\n```"
        return {"answer": ans}

    if len(rows) == 1 and isinstance(rows[0], dict):
        keys = list(rows[0].keys())
        if len(keys) == 1 and any(k.lower() in ['count', 'total', 'n', 'cantidad'] for k in keys):
            value = rows[0][keys[0]]
            ans = f"✅ **Resultado:** {value}\n\n**Base de datos:** {db_name}\n**SQL:**\n```sql\n{sql_used}\n```"
            return {"answer": ans}

    formatted = fmt_rows(rows)
    row_count = len(rows)
    ans = (
        f"✅ **Encontré {row_count} registro(s)**\n\n"
        f"**Base de datos:** {db_name}\n"
        f"**SQL usado:**\n```sql\n{sql_used}\n```\n\n"
        f"```\n{formatted}\n```"
    )

    if strategy_name:
        ans += f"\n\n🧠 **Estrategia usada:** {strategy_name}"
    if strategies:
        ans += f"\n🧠 **Estrategias evaluadas:** {state.get('strategy_index', 0) + 1}"
    if retry_count > 0:
        ans += f"\n🧠 **Alternativas CoT:** {retry_count}"

    return {"answer": clip_out(ans)}

# ---------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("input", node_input)
    g.add_node("supervisor", node_supervisor)
    g.add_node("generate_strategies", node_generate_strategies)
    g.add_node("postgres", node_postgres_agent)
    g.add_node("next_strategy", node_next_strategy)
    g.add_node("generate_alternative", node_generate_alternative)
    g.add_node("clarify", node_clarify)
    g.add_node("done", node_done)

    g.set_entry_point("input")
    g.add_edge("input", "supervisor")

    g.add_conditional_edges(
        "supervisor",
        decide_after_supervisor,
        {
            "postgres": "postgres",
            "strategies": "generate_strategies",
            "clarify": "clarify",
            "done": "done",
        },
    )

    g.add_edge("generate_strategies", "postgres")

    g.add_conditional_edges(
        "postgres",
        should_after_postgres,
        {
            "done": "done",
            "clarify": "clarify",
            "alternative": "generate_alternative",
            "next_strategy": "next_strategy",
        },
    )

    g.add_edge("next_strategy", "postgres")
    g.add_edge("generate_alternative", "postgres")
    g.add_edge("clarify", END)
    g.add_edge("done", END)
    return g.compile()

GRAPH = build_graph() if LANGGRAPH_OK else None

# ---------------------------------------------------------------------
# OpenWebUI Pipeline wrapper
# ---------------------------------------------------------------------
class Pipeline:
    id = "jp_agent_unificado_cot_multi_db"
    name = "JP - Agente Unificado CoT"

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
        yield "data: [DONE]\n\n"

    def pipe(self, body: dict, **kwargs):
        if not LANGGRAPH_OK:
            msg = f"❌ LangGraph no disponible: {LANGGRAPH_ERR}\n\nInstala langgraph: `pip install langgraph`"
            return self._sse_stream(msg) if body.get("stream") else self._wrap_nonstream(msg)

        try:
            messages = body.get("messages", []) or []
            user_text_str = (messages[-1].get("content") if messages else "") or ""
            low = user_text_str.strip().lower()

            user_info = kwargs.get("__user__", {}) or {}
            user_id = str(user_info.get("id", "anonymous"))
            conversation_id = hashlib.md5(user_id.encode()).hexdigest()[:16]

            if low in {"hola", "hello", "hi", "buenas", "buenos dias", "buenas tardes", "buenas noches", "hey"}:
                ans = (
                    "¡Hola! 👋 Soy tu asistente de bases de datos.\n\n"
                    "Puedo:\n"
                    "• elegir automáticamente qué agente/BD usar\n"
                    "• consultar tablas y columnas\n"
                    "• aplicar CoT cuando la consulta es ambigua\n"
                    "• repreguntar si falta contexto\n\n"
                    "Ejemplos:\n"
                    "• _\"¿Qué bases de datos tengo disponibles?\"_\n"
                    "• _\"Muéstrame las tablas de enel\"_\n"
                    "• _\"Dame 20 registros de la tabla tratamiento\"_"
                )
                return self._sse_stream(ans) if body.get("stream") else self._wrap_nonstream(ans)

            if low in {"ayuda", "help", "?", "que puedes hacer", "qué puedes hacer"}:
                ans = (
                    "🤖 **¿Qué puedo hacer por ti?**\n\n"
                    + get_db_info_text()
                    + "\n\n**Ejemplos de preguntas:**\n"
                    "• Ver tablas: _\"Muéstrame las tablas de enel\"_\n"
                    "• Contar registros: _\"Cuántos registros hay en usuarios\"_\n"
                    "• Ver datos: _\"Dame 20 registros de la tabla tratamiento\"_\n"
                    "• Explorar: _\"Qué columnas tiene la tabla clientes\"_"
                )
                return self._sse_stream(ans) if body.get("stream") else self._wrap_nonstream(ans)

            if low in {"contexto", "bd"}:
                current = CONVERSATION_CONTEXT.get(conversation_id, "ncorrea (default)")
                ans = f"🗂️ **BD actual/contexto:** {current}"
                return self._sse_stream(ans) if body.get("stream") else self._wrap_nonstream(ans)

            out = GRAPH.invoke({"user_text": user_text_str, "conversation_id": conversation_id, "messages_history": messages}) if GRAPH else {"answer": "❌ Grafo no inicializado."}
            ans = out.get("answer", "Lo siento, no pude procesar tu solicitud. ¿Podrías reformularla?")

            return self._sse_stream(ans) if body.get("stream") else self._wrap_nonstream(ans)
        except Exception as e:
            msg = f"❌ **Error interno:** {type(e).__name__}: {e}"
            if DEBUG_MODE:
                import traceback
                msg += f"\n\n```\n{traceback.format_exc()}\n```"
            return self._sse_stream(msg) if body.get("stream") else self._wrap_nonstream(msg)