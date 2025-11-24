# Code for the Query Agent

from llm.client import LLMClient

class QueryAgent:
    def __init__(self):
        self.llm = LLMClient()

    async def run(self, text_query: str):
        prompt = (
            "Eres un experto en interpretar y traducir lenguaje natural a SQL. "
            "Convierte el prompt del usuario realizado con lenguaje natural language a SQL, para una base de datos PostgreSQL. "
            "Solo devuelve la sentencia SQL, sin explicaciones.\n\n"
            f"Input: {text_query}\nSQL:"
        )

        sql = await self.llm.ask(prompt)
        return {"sql": sql.strip()}
