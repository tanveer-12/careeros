from typing import Optional
from config.settings import settings

class LLMClient:
    def __init__(self):
        self.enabled = settings.LLM_ENABLED
        self.provider = settings.LLM_PROVIDER

    async def achat(self, prompt:str, system:Optional[str] = None, **kwargs) -> str:
        if not self.enabled:
            return "LLM is disabled in this mode."
        
        if self.provider == "huggingface_api":
            # Stub for now; you’ll implement HTTP call later
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "http://localhost:8080/v1/chat/completions",
                    json={
                        "model": settings.LLM_MODEL,
                        "messages": [
                            {"role": "system", "content": system} if system else None,
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                        **kwargs
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        else:
            raise NotImplementedError(f"LLM provider {self.provider!r} not yet implemented.")
        
llm_client = LLMClient()
