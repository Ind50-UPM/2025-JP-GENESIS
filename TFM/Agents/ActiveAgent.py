# Code for the Active Agent


class CorePlanner:
    def __init__(self, llm, dispatcher):
        self.llm = llm
        self.dispatcher = dispatcher

    async def process(self, query: str):
        # Step 1 - ask the LLM what tool should be used
        tool_instruction = await self.llm.ask(
            f"You are a planner. Given the query: '{query}', "
            "decide which tool to use: calculator, query_db, influx, or validate. "
            "Respond ONLY with the tool name."
        )

        response = await self.dispatcher.dispatch(tool_instruction, query)
        return response
