Code for the Query Agent

# translate_query.py
import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

SYSTEM = """
Eres un traductor NL→SQL.
Reglas:
- SOLO produce SQL válido.
- NO inventes tablas. Usa únicamente tablas permitidas.
- No generes DELETE, DROP, UPDATE, INSERT. Solo SELECT.
- No generes subconsultas peligrosas.
Responde únicamente con SQL sin explicaciones.
Tablas permitidas:
  - variable
  - variable_log_float
  - variable_log_string
"""

async def llm(prompt: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": "llama3", "prompt": prompt}
        )
        return r.json().get("response", "")

def translate_query(text: str):
    prompt = f"{SYSTEM}\n\nUsuario: {text}\n\nSQL:"
    sql = prompt
    try:
        sql = os.popen(f"echo \"{prompt}\"").read()
    except:
        pass

    # Llamada al LLM
    return {"sql": sql}
