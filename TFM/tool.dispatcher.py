# tool_dispatcher.py
from agent.tools.translate_query import translate_query
from agent.tools.run_query import run_query
from agent.tools.calc_stats import calc_stats
from agent.tools.influx_agent import InfluxDBAgent
import asyncio

async def dispatch_tool(name: str, args: dict):

    if name == "calculator":
        from agent.tools.calculator_agent import calculator_tool
        return calculator_tool(args.get("expression"))

    if name == "influxdb_query":
        from agent.tools.influxdb_agent import influxdb_query
        return await influxdb_query(**args)

    if name == "query_agent":
        from agent.tools.query_agent import execute_structured_query
        return await execute_structured_query(**args)

    if name == "validate_response":
        from agent.tools.validate_response import validate_response
        return await validate_response(
            question=args.get("question", ""),
            llm_response=args.get("response", "")
        )

    return {"error": f"unknown tool {name}"}
