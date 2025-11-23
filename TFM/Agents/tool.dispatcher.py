# tool_dispatcher.py


from agent.tools.calculator import CalculatorAgent
from agent.tools.db_agent import DBQueryAgent
from agent.tools.influx_agent import InfluxAgent
from agent.tools.query_agent import QueryAgent
from agent.tools.validator_agent import ValidatorAgent

class ToolDispatcher:
    def __init__(self):
        self.tools = {
            "calculator": CalculatorAgent(),
            "query_db": DBQueryAgent(),
            "influx": InfluxAgent(),
            "transform_query": QueryAgent(),
            "validate": ValidatorAgent()
        }

    async def dispatch(self, tool_name: str, query: str):
        tool_name = tool_name.strip().lower()

        if tool_name not in self.tools:
            return f"Herramienta no registrada: {tool_name}"

        return await self.tools[tool_name].run(query)

