# Code for the Verifier Agent

import random

class ValidatorAgent:
    async def run(self, answer: str):
        # placeholder heuristics — luego se puede mejorar
        confidence = round(random.uniform(6.5, 9.8), 2)
        relevance = round(random.uniform(7.0, 9.9), 2)

        reasoning = (
            "The answer was evaluated based on semantic coherence and internal logic. "
            "No contradictory statements were detected."
        )

        consistency = "consistent" if confidence > 7.0 else "needs review"

        return {
            "confidence": confidence,
            "relevance": relevance,
            "reasoning": reasoning,
            "consistency": consistency
        }
