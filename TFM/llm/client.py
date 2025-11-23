import asyncio
import httpx

class LLMClient:
    def __init__(self, base_url="http://localhost:11434/api/generate", model="llama3"):
        self.base_url = base_url
        self.model = model

    async def ask(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(self.base_url, json=payload)
            return r.json()["response"]
