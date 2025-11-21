Code for the Verifier Agent


# validate_response.py
import os
import httpx
import json
from typing import Dict, Any

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")


SYSTEM_PROMPT = """
Eres un agente evaluador de calidad de respuestas generadas por LLMs.
Tu función es analizar una respuesta y evaluar:

1. CONFIANZA (1 a 10, con máximo dos decimales):
   - Evalúa exactitud, claridad, solidez de razonamiento.
   - No inventes información, solo analiza lo dado.

2. RAZONAMIENTO:
   - Explica brevemente por qué asignaste esa confianza.
   - Debe ser claro y justificable.

3. RELEVANCIA (1 a 10, con máximo dos decimales):
   - Qué tan alineada está la respuesta con la pregunta original.

4. CONSISTENCIA DE DATOS:
   - Verifica si hay contradicciones internas, incoherencias o afirmaciones imposibles.
   - Responde con: "Consistente", "Inconsistente" o "Incierto".

El formato de salida debe ser un JSON válido EXACTO como este:

{
  "confianza": 0.00,
  "razonamiento": "texto...",
  "relevancia": 0.00,
  "consistencia": "Consistente / Inconsistente / Incierto",
  "explicacion_consistencia": "texto..."
}

No incluyas nada más fuera de este JSON.
"""

async def call_llm(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": "llama3", "prompt": prompt},
        )
        return r.json().get("response", "").strip()

async def validate_response(question: str, llm_response: str) -> Dict[str, Any]:
    """
    Evalúa la calidad de una respuesta generada por un LLM.
    """
    
    prompt = f"""{SYSTEM_PROMPT}

PREGUNTA ORIGINAL:
{question}

RESPUESTA DEL LLM:
{llm_response}

Genera la evaluación ahora:
"""

    raw = await call_llm(prompt)

    # Intentar parsear JSON
    try:
        data = json.loads(raw)
    except:
        data = {
            "confianza": 0.0,
            "razonamiento": "Error al generar JSON.",
            "relevancia": 0.0,
            "consistencia": "Incierto",
            "explicacion_consistencia": "El modelo devolvió un formato inesperado."
        }

    return data
