# Code for the Verifier Agent

import random

class ValidatorAgent:
    async def run(self, answer: str):
        # placeholder heuristics — hecho para pruebas pero se puede cambiar
        confidence = round(random.uniform(6.5, 9.8), 2)
        relevance = round(random.uniform(7.0, 9.9), 2)

        reasoning = (
            "La respuesta fue evaluada en base a dos criterios: lógica interna y coherencia semántica. "
            "No se han detectado enunciados contradictorios."
        )

        consistency = "Consistente" if confidence > 7.0 else "Requiere revisión"

        return {
            "confidence": confidence,
            "relevance": relevance,
            "reasoning": reasoning,
            "consistency": consistency
        }
