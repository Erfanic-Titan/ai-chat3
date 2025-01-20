# handlers/deepseek_handler.py
import aiohttp
import json
from typing import Optional, AsyncGenerator
import logging

logger = logging.getLogger(__name__)

class DeepSeekHandler:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_base = "https://api.deepseek.com/v1/chat/completions"
        self.models = {
            "deepseek-v3": "deepseek-chat-v3"  # اصلاح نام مدل
        }
    
    async def process_content(
        self,
        content: str,
        content_type: str,
        file_path: Optional[str] = None,
        model_version: str = "deepseek-v3",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        try:
            if content_type != "text":
                raise ValueError("DeepSeek only supports text input")
            
            model = self.models.get(model_version)
            if not model:
                raise ValueError(f"Model version {model_version} not supported")
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": model,
                "messages": [{"role": "user", "content": content}],
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2048),
                "stream": True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_base,
                    headers=headers,
                    json=data
                ) as response:
                    if response.status != 200:
                        error_data = await response.json()
                        raise ValueError(f"API Error: {error_data.get('error', 'Unknown error')}")
                    
                    buffer = ""
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if not line or line == "data: [DONE]":
                            continue
                            
                        if line.startswith("data: "):
                            try:
                                chunk_data = json.loads(line[6:])
                                if chunk_data.get("choices") and chunk_data["choices"][0].get("delta", {}).get("content"):
                                    text = chunk_data["choices"][0]["delta"]["content"]
                                    buffer += text
                                    
                                    if any(c in buffer for c in ['.', '!', '?', '\n']) or len(buffer) > 80:
                                        yield buffer
                                        buffer = ""
                            except json.JSONDecodeError:
                                continue
                    
                    if buffer:
                        yield buffer
        
        except Exception as e:
            logger.error(f"DeepSeek processing error: {str(e)}")
            yield f"Error: {str(e)}"
    
    def get_available_parameters(self, model_version: str) -> dict:
        return {
            "temperature": {
                "type": "float",
                "min": 0.0,
                "max": 1.0,
                "default": 0.7,
                "description": "Controls randomness in responses"
            },
            "max_tokens": {
                "type": "int",
                "min": 1,
                "max": 2048,
                "default": 2048,
                "description": "Maximum response length"
            }
        }