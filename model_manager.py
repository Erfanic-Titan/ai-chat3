# model_manager.py
from typing import Optional, Dict, Any, AsyncGenerator
from handlers.gemini_handler import GeminiHandler
from handlers.claude_handler import ClaudeHandler
from handlers.deepseek_handler import DeepSeekHandler
from config import MODELS
import logging
from config import DEFAULT_PARAMS

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, gemini_api_key: str, claude_api_key: str, deepseek_api_key: str):
        self.handlers = {
            "gemini": GeminiHandler(gemini_api_key),
            "claude": ClaudeHandler(claude_api_key),
            "deepseek": DeepSeekHandler(deepseek_api_key)
        }
        self._model_params = {}  # Store model parameters

    def get_available_models(self) -> Dict[str, list]:
        """Get all available models and their versions"""
        return {
            model_name: model_info["versions"]
            for model_name, model_info in MODELS.items()
        }
    

    def get_supported_inputs(self, model_name: str) -> list:
        """Get supported input types for a model"""
        return MODELS[model_name]["supported_inputs"]
    
    def get_model_parameters(self, model_name: str, model_version: str) -> dict:
        """Get available parameters for a specific model and version"""
        if model_name not in self.handlers:
            raise ValueError(f"Unknown model: {model_name}")
        return self.handlers[model_name].get_available_parameters(model_version)
    
    async def update_model_params(
        self,
        model_name: str,
        model_version: str,
        params: Dict[str, Any]
    ) -> bool:
        """Update model parameters and return success status"""
        try:
            logger.info(f"Updating parameters for {model_name} ({model_version})")
            logger.info(f"New parameters: {params}")

            if model_name not in self.handlers:
                logger.error(f"Unknown model: {model_name}")
                return False
            
            # Validate and sanitize parameters
            validated_params = {}
            for param, value in params.items():
                if param in ["temperature", "top_p", "top_k", "max_tokens"]:
                    try:
                        if param in ["top_k", "max_tokens"]:
                            value = int(float(value))
                        else:
                            value = float(value)
                        validated_params[param] = value
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error validating parameter {param}: {str(e)}")
                        continue

            # Store parameters
            key = f"{model_name}_{model_version}"
            self._model_params[key] = validated_params
            logger.info(f"Parameters updated successfully: {validated_params}")
            
            # Update handler if it supports parameter updates
            handler = self.handlers[model_name]
            if hasattr(handler, "update_params"):
                await handler.update_params(model_version, validated_params)
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating model parameters: {str(e)}", exc_info=True)
            return False

    def get_current_params(self, model_name: str, model_version: str) -> Dict[str, Any]:
        """Get current parameters for a specific model and version"""
        key = f"{model_name}_{model_version}"
        return self._model_params.get(key, DEFAULT_PARAMS.copy())
        
    async def process_content(
        self,
        model_name: str,
        model_version: str,
        content: str,
        content_type: str = "text",
        file_path: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Process content with specified model"""
        try:
            if model_name not in self.handlers:
                raise ValueError(f"Unknown model: {model_name}")

            if content_type not in MODELS[model_name]["supported_inputs"]:
                raise ValueError(f"Input type {content_type} not supported by {model_name}")

            handler = self.handlers[model_name]
            async for chunk in handler.process_content(
                content=content,
                content_type=content_type,
                file_path=file_path,
                model_version=model_version,
                **kwargs
            ):
                yield chunk

        except Exception as e:
            logger.error(f"Error processing content with {model_name}: {str(e)}")
            yield f"Error: {str(e)}"

    def get_param_info(self, model_name: str, param: str) -> dict:
        """Get parameter info for a specific model"""
        if model_name not in self.handlers:
            raise ValueError(f"Unknown model: {model_name}")
            
        params = self.handlers[model_name].get_available_parameters(model_name)
        param_info = params.get(param)
        
        if not param_info:
            raise ValueError(f"Parameter {param} not found for model {model_name}")
            
        return param_info