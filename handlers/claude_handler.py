# handlers/claude_handler.py
from anthropic import Anthropic
from typing import Optional, AsyncGenerator
import base64
import mimetypes
import os
import asyncio
import logging

logger = logging.getLogger(__name__)

class ClaudeHandler:
    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.models = {
            "claude-3.5-haiku": "claude-3.5-haiku-20240307",
            "claude-3.5-sonnet": "claude-3.5-sonnet-20240307"
        }
    
    def _encode_image(self, file_path: str) -> str:
        """Encode image to base64"""
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    async def process_content(
        self,
        content: str,
        content_type: str,
        file_path: Optional[str] = None,
        model_version: str = "claude-3.5-sonnet",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Process content and return response"""
        try:
            model = self.models.get(model_version)
            if not model:
                raise ValueError(f"Model version {model_version} not supported")

            messages = []
            
            if content_type == "image":
                if not file_path or not os.path.exists(file_path):
                    raise ValueError("Image file not found")
                
                mime_type = mimetypes.guess_type(file_path)[0]
                if not mime_type or not mime_type.startswith('image/'):
                    raise ValueError("Invalid image file")
                
                image_data = self._encode_image(file_path)
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": content
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": image_data
                            }
                        }
                    ]
                })
            else:
                messages.append({
                    "role": "user",
                    "content": content
                })

            response = await self.client.messages.create(
                model=model,
                max_tokens=kwargs.get('max_tokens', 4096),
                temperature=kwargs.get('temperature', 0.7),
                messages=messages
            )

            full_response = response.content[0].text
            chunk_size = 50
            for i in range(0, len(full_response), chunk_size):
                chunk = full_response[i:i + chunk_size]
                yield chunk
                await asyncio.sleep(0.05)

        except Exception as e:
            logger.error(f"Claude processing error: {str(e)}")
            yield f"Error: {str(e)}"

    def get_available_parameters(self, model_version: str) -> dict:
        """Get available parameters for the specified model version"""
        return {
            "temperature": {
                "type": "float",
                "min": 0.0,
                "max": 1.0,
                "default": 0.7,
                "description": "Controls randomness in the response"
            },
            "max_tokens": {
                "type": "int",
                "min": 1,
                "max": 4096,
                "default": 4096,
                "description": "Maximum length of the response"
            }
        }