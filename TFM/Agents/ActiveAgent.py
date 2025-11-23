Code for the Active Agent


# core_planner.py
import json
from typing import List, Dict, Any
from agent.tool_dispatcher import dispatch_tool
from utils.json_validator import validate_agent_json
import os
import httpx

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

SYSTEM_PROMPT = open("config/system_prompt_agentic.txt").read()

async def call_llm(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{OLLAMA_URL}/api/generate", json={"model":"llama3","prompt":prompt})
        return r.text if r.status_code!=200 else r.json().get("response","")

async def process_user_message(messages: List[Dict[str,Any]]) -> Dict[str,Any]:
    # Build prompt including tool specs (short)
    user_text = messages[-1]['content']
    prompt = f"{SYSTEM_PROMPT}\n\nUSER:\n{user_text}\n\nReturn ONLY valid JSON."
    llm_resp = await call_llm(prompt)
    parsed = validate_agent_json(llm_resp)
    # If final answer -> return
    if "final_answer" in parsed:
        return parsed
    # If action -> dispatch tool
    if "action" in parsed:
        tool = parsed["action"]["tool"]
        args = parsed["action"]["args"]
        res = await dispatch_tool(tool, args)
        # feed result back to LLM
        followup = f"{SYSTEM_PROMPT}\n\nUSER:\n{user_text}\n\nTOOL_RESULT:\n{res}\n\nReturn ONLY valid JSON."
        llm2 = await call_llm(followup)
        return validate_agent_json(llm2)
    return parsed
