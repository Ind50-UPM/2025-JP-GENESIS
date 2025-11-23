# Code for the Active Agent


class CorePlanner:
    def __init__(self, llm, dispatcher):
        self.llm = llm
        self.dispatcher = dispatcher

    async def process(self, query: str):
        # Preguntar al LLM cuál herramienta debe ser usada
        tool_instruction = await self.llm.ask(
            f"Eres un administrador encargado de planificaciones. Dada la query: '{query}', "
            "decide cuál herramienta se debe usar: calculatoragent, agentdb, queryagent, influxdbagent, o verifieragent. "
            "Responde solo con el nombre de la herramienta."
        )

        response = await self.dispatcher.dispatch(tool_instruction, query)
        return response
