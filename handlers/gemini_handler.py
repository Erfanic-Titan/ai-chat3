# handlers/gemini_handler.py
import google.generativeai as genai
from typing import Optional, AsyncGenerator, List, Dict
import mimetypes
import os
import logging
from PIL import Image
import io
import base64
from config import MODELS
import asyncio

logger = logging.getLogger(__name__)

class GeminiHandler:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.models = {}
        self._initialize_models()
        
        # Track active conversations
        self.active_chats = {}
    
    def _initialize_models(self):
        """Initialize different Gemini model versions"""
        model_versions = [
            "gemini-1.5-flash-002",
            "gemini-1.5-pro-002",
            "gemini-2.0-flash-exp"
        ]
        for version in model_versions:
            try:
                self.models[version] = genai.GenerativeModel(version)
            except Exception as e:
                logger.error(f"Failed to initialize {version}: {str(e)}")

    def _validate_file(self, file_path: str, content_type: str) -> bool:
        """Validate file format and size"""
        if not os.path.exists(file_path):
            raise ValueError("File not found")
            
        file_size = os.path.getsize(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if content_type not in MODELS["gemini"]["supported_formats"]:
            raise ValueError(f"Unsupported content type: {content_type}")
            
        supported_formats = MODELS["gemini"]["supported_formats"][content_type]
        limits = MODELS["gemini"]["limits"][content_type]
        
        if file_ext not in supported_formats:
            raise ValueError(
                f"Unsupported file format. Supported formats: {', '.join(supported_formats)}"
            )
        
        if file_size > limits["max_size"]:
            raise ValueError(
                f"File too large. Maximum size: {limits['max_size'] / (1024 * 1024):.1f}MB"
            )
        
        return True

    def _process_image(self, file_path: str) -> Dict:
        """Process image file for Gemini"""
        self._validate_file(file_path, "image")
        
        try:
            with Image.open(file_path) as img:
                # Validate image mode
                if img.format.upper() not in ['JPEG', 'PNG', 'WEBP', 'HEIC', 'HEIF', 'GIF']:
                    img = img.convert('RGB')
                
                # Check and adjust resolution if needed
                max_res = MODELS["gemini"]["limits"]["image"]["max_resolution"]
                if img.width > max_res or img.height > max_res:
                    ratio = max_res / max(img.width, img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Save to bytes with optimal quality
                img_byte_arr = io.BytesIO()
                save_format = 'JPEG' if img.mode == 'RGB' else 'PNG'
                
                if save_format == 'JPEG':
                    img.save(img_byte_arr, format=save_format, quality=85, optimize=True)
                else:
                    img.save(img_byte_arr, format=save_format, optimize=True)
                
                img_byte_arr = img_byte_arr.getvalue()
                
                mime_type = f"image/{save_format.lower()}"
                
                return {
                    "mime_type": mime_type,
                    "data": img_byte_arr
                }
                
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            raise ValueError(f"Error processing image: {str(e)}")

    def _process_video(self, file_path: str) -> Dict:
        """Process video file for Gemini"""
        self._validate_file(file_path, "video")
        
        try:
            # Add video validation (duration, resolution, etc.)
            limits = MODELS["gemini"]["limits"]["video"]
            
            mime_type = mimetypes.guess_type(file_path)[0]
            if not mime_type or mime_type not in limits["supported_mime_types"]:
                raise ValueError(f"Unsupported video format: {mime_type}")
            
            with open(file_path, 'rb') as f:
                video_data = f.read()
                
            return {
                "mime_type": mime_type,
                "data": video_data
            }
            
        except Exception as e:
            logger.error(f"Error processing video: {str(e)}")
            raise ValueError(f"Error processing video: {str(e)}")

    def _process_audio(self, file_path: str) -> Dict:
        """Process audio file for Gemini"""
        self._validate_file(file_path, "audio")
        
        try:
            # Add audio validation (duration, format, etc.)
            limits = MODELS["gemini"]["limits"]["audio"]
            
            mime_type = mimetypes.guess_type(file_path)[0]
            if not mime_type or mime_type not in limits["supported_mime_types"]:
                raise ValueError(f"Unsupported audio format: {mime_type}")
            
            with open(file_path, 'rb') as f:
                audio_data = f.read()
                
            return {
                "mime_type": mime_type,
                "data": audio_data
            }
            
        except Exception as e:
            logger.error(f"Error processing audio: {str(e)}")
            raise ValueError(f"Error processing audio: {str(e)}")

    def _process_document(self, file_path: str) -> Dict:
        """Process document file for Gemini"""
        self._validate_file(file_path, "document")
        
        try:
            limits = MODELS["gemini"]["limits"]["document"]
            
            # Read document content
            with open(file_path, 'rb') as f:
                doc_data = f.read()
                
            mime_type = mimetypes.guess_type(file_path)[0]
            if not mime_type:
                mime_type = 'application/octet-stream'
                
            return {
                "mime_type": mime_type,
                "data": doc_data
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            raise ValueError(f"Error processing document: {str(e)}")

    def _format_chat_history(self, history: List[Dict]) -> List[Dict]:
        """Format chat history for Gemini model"""
        formatted_history = []
        for msg in history:
            if msg["role"] == "user":
                formatted_history.append({
                    "role": "user",
                    "parts": [msg["content"]]
                })
            elif msg["role"] == "assistant":
                formatted_history.append({
                    "role": "model",
                    "parts": [msg["content"]]
                })
        return formatted_history

    async def process_content(
        self, 
        content: str, 
        content_type: str = "text",
        chat_history: List[Dict] = None,
        file_path: Optional[str] = None,
        model_version: str = "gemini-1.5-flash-002",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        try:
            # Validate content
            if not content or not content.strip():
                content = "Please help me analyze this" if file_path else "Hello"
            
            model = self.models.get(model_version)
            if not model:
                raise ValueError(f"Model version {model_version} not initialized")
                
            generation_config = {
                "temperature": float(kwargs.get("temperature", 0.7)),
                "top_p": float(kwargs.get("top_p", 0.95)),
                "top_k": int(kwargs.get("top_k", 40)),
                "max_output_tokens": int(kwargs.get("max_tokens", 2048)),
            }
            
            model.generation_config = generation_config
            
            # Format chat history
            formatted_history = []
            if chat_history:
                for msg in chat_history:
                    if msg["content"].strip():  # Only add non-empty messages
                        formatted_history.append({
                            "role": "user" if msg["role"] == "user" else "model",
                            "parts": [msg["content"]]
                        })
            
            chat = model.start_chat(history=formatted_history)
            prompt_parts = [content.strip()]
            
            # Handle non-text content
            if content_type != "text" and file_path:
                try:
                    if content_type == "image":
                        media_data = self._process_image(file_path)
                    elif content_type == "video":
                        media_data = self._process_video(file_path)
                    elif content_type == "audio":
                        media_data = self._process_audio(file_path)
                    elif content_type == "document":
                        media_data = self._process_document(file_path)
                    else:
                        raise ValueError(f"Unsupported content type: {content_type}")
                        
                    prompt_parts.append({
                        "mime_type": media_data["mime_type"],
                        "data": media_data["data"]
                    })
                except Exception as e:
                    logger.error(f"Error processing {content_type}: {str(e)}")
                    yield f"Error processing {content_type}: {str(e)}"
                    return
            
            try:
                response = await asyncio.to_thread(
                    chat.send_message,
                    prompt_parts,
                    stream=True
                )
                
                async for chunk in self._process_response_stream(response):
                    yield chunk
                    
            except Exception as e:
                error_msg = str(e).lower()
                if "empty text parameter" in error_msg:
                    yield "I apologize, but I couldn't process an empty message. Please provide some text or context."
                else:
                    logger.error(f"Gemini processing error: {str(e)}")
                    yield f"Error: {str(e)}"
                    
        except Exception as e:
            logger.error(f"Gemini processing error: {str(e)}")
            yield f"Error: {str(e)}"

    async def _process_response_stream(self, response, max_retries=3):
        """Process streaming response from Gemini with retry logic"""
        retry_count = 0
        while retry_count < max_retries:
            try:
                for chunk in response:
                    if hasattr(chunk, 'text'):
                        yield chunk.text
                        await asyncio.sleep(0.02)  # Prevent flooding
                break  # Success, exit loop
                
            except Exception as e:
                error_message = str(e).lower()
                retry_count += 1
                
                if "503" in error_message or "overloaded" in error_message:
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count  # Exponential backoff
                        logger.warning(f"Model overloaded, retrying in {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error("Max retries reached for model overload")
                        yield "\n\n⚠️ The model is currently experiencing high load. Please try regenerating the response."
                        break
                else:
                    logger.error(f"Error in response streaming: {str(e)}")
                    yield f"\n\nError: {str(e)}"
                    break
    
    def get_available_parameters(self, model_version: str) -> dict:
        """Get available parameters for the specified model version"""
        return {
            "temperature": {
                "type": "float",
                "min": 0.0,
                "max": 2.0,
                "default": 0.7,
                "description": "Controls randomness in responses",
                "detail": "Higher values make output more creative but less predictable"
            },
            "top_p": {
                "type": "float",
                "min": 0.0,
                "max": 1.0,
                "default": 0.95,
                "description": "Controls diversity via nucleus sampling",
                "detail": "Higher values consider more possibilities"
            },
            "top_k": {
                "type": "int",
                "min": 1,
                "max": 100,
                "default": 40,
                "description": "Controls vocabulary restriction",
                "detail": "Lower values make output more focused"
            },
            "max_tokens": {
                "type": "int",
                "min": 1,
                "max": 8192,
                "default": 2048,
                "description": "Maximum response length",
                "detail": "Higher values allow longer responses"
            }
        }

    def validate_parameters(self, params: Dict) -> Dict:
        """Validate and sanitize parameters"""
        available_params = self.get_available_parameters("")
        validated_params = {}
        
        for key, value in params.items():
            if key in available_params:
                param_info = available_params[key]
                try:
                    if param_info["type"] == "float":
                        value = float(value)
                    elif param_info["type"] == "int":
                        value = int(value)
                        
                    value = max(param_info["min"], min(param_info["max"], value))
                    validated_params[key] = value
                except (ValueError, TypeError):
                    validated_params[key] = param_info["default"]
        
        return validated_params