# tool_dispatcher.py
from agent.tools.translate_query import translate_query
from agent.tools.run_query import run_query
from agent.tools.calc_stats import calc_stats
from agent.tools.influx_agent import InfluxDBAgent
import asyncio

async def dispatch_tool(name: str, args: dict):
    if name == "translate_query":
        return translate_query(args.get("text",""))
    if name == "run_query":
        return await run_query(args.get("sql",""))
    if name == "calc_stats":
        return calc_stats(args.get("operation",""), args.get("values",[]))
    if name == "influx_query":
        agent = InfluxDBAgent()
        return agent.run(args)
    return {"error":"unknown tool"}
