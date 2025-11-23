# Code for the Query Agent

from llm.client import LLMClient

class QueryAgent:
    def __init__(self):
        self.llm = LLMClient()

    async def run(self, text_query: str):
        prompt = (
            "Convert the following natural language request into SQL for a PostgreSQL database. "
            "Return ONLY the SQL, no explanation.\n\n"
            f"Input: {text_query}\nSQL:"
        )

        sql = await self.llm.ask(prompt)
        return {"sql": sql.strip()}
