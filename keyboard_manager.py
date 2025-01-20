# keyboard_manager.py
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict, Optional, Union
from config import MODELS, DEFAULT_PARAMS, PARAMETER_CONFIG
from config import SUPPORTED_LANGUAGES

class KeyboardManager:
    @staticmethod
    def format_param_value(value: Union[float, int], precision: int = 1) -> str:
        """Format parameter value with consistent precision"""
        try:
            if precision == 0:
                return str(int(float(value)))
            return f"{float(value):.{precision}f}"
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def get_model_selection_keyboard() -> InlineKeyboardMarkup:
        """Get keyboard for initial model selection"""
        keyboard = [
            [InlineKeyboardButton("✨ Google Gemini", callback_data="select_model:gemini")],
            [InlineKeyboardButton("🧠 Anthropic Claude", callback_data="select_model:claude")],
            [InlineKeyboardButton("🐳 DeepSeek", callback_data="select_model:deepseek")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_options")] 
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_model_version_keyboard(model: str, versions: List[str]) -> InlineKeyboardMarkup:
        """Get keyboard for model version selection"""
        version_icons = {
            "gemini-1.5-flash-002": "⚡",
            "gemini-1.5-pro-002": "⭐️",
            "gemini-2.0-flash": "💫",
            "claude-3.5-haiku": "🎯",
            "claude-3.5-sonnet": "🎭",
            "deepseek-v3": "🔮"
        }
        
        keyboard = []
        for version in versions:
            keyboard.append([
                InlineKeyboardButton(
                    f"{version_icons.get(version, '🤖')} {version}",
                    callback_data=f"select_version:{model}:{version}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔙 Back", callback_data="back_to_models")
        ])
        
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_chat_options_keyboard() -> InlineKeyboardMarkup:
        """Get keyboard for chat options"""
        keyboard = [
            [
                InlineKeyboardButton("🆕 New Chat", callback_data="new_chat"),
                InlineKeyboardButton("💬 Previous Chats", callback_data="select_chat")
            ],
            [
                InlineKeyboardButton("⚙️ Model Settings", callback_data="model_settings"),
                InlineKeyboardButton("🔄 Change Model", callback_data="change_model")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_models")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_chat_management_keyboard(chat_id: int) -> InlineKeyboardMarkup:
        """Get keyboard for managing a specific chat"""
        keyboard = [
            [
                InlineKeyboardButton(
                    "✏️ Rename",
                    callback_data=f"rename_chat:{chat_id}"
                ),
                InlineKeyboardButton(
                    "🗑️ Delete",
                    callback_data=f"delete_chat:{chat_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    " 🌐 Language",
                    callback_data=f"select_lang:{chat_id}"
                )
            ],
            [
            InlineKeyboardButton(
                "📥 Export Chat",
                callback_data=f"export_chat:{chat_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back to Chats",
                    callback_data="back_to_chats"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_chat_list_keyboard(chats: List[Dict]) -> InlineKeyboardMarkup:
        """Get keyboard for chat list"""
        keyboard = []
        for chat in chats:
            keyboard.append([
                InlineKeyboardButton(
                    f"💬 {chat['title']}",
                    callback_data=f"select_chat:{chat['chat_id']}"
                ),
                InlineKeyboardButton(
                    "⚙️",
                    callback_data=f"manage_chat:{chat['chat_id']}"
                )
            ])
        
        keyboard.extend([
            [InlineKeyboardButton("➕ New Chat", callback_data="new_chat")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_options")]
        ])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_message_actions_keyboard(message_id: int) -> InlineKeyboardMarkup:
        """Get keyboard for message actions"""
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 Regenerate",
                    callback_data=f"regenerate:{message_id}"
                ),
                InlineKeyboardButton(
                    "⚙️ Advanced Settings",
                    callback_data="settings:advanced"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="back_to_options"
                    )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_settings_keyboard(model: str, current_params: Dict) -> InlineKeyboardMarkup:
        """Get keyboard for model settings"""
        keyboard = []
        
        # Make sure we have all parameters with default values
        all_params = {
            "temperature": DEFAULT_PARAMS["temperature"],
            "top_p": DEFAULT_PARAMS["top_p"],
            "top_k": DEFAULT_PARAMS["top_k"],
            "max_tokens": DEFAULT_PARAMS["max_tokens"]
        }
        all_params.update(current_params)

        # Parameter adjustment buttons
        for param in ["temperature", "top_p", "top_k", "max_tokens"]:
            if param in current_params and param in PARAMETER_CONFIG:
                formatted_value = KeyboardManager.format_param_value(
                    current_params[param],
                    PARAMETER_CONFIG[param]["precision"]
                )
                keyboard.append([
                    InlineKeyboardButton(
                        f"{KeyboardManager._get_param_icon(param)} {param.replace('_', ' ').title()}: {formatted_value}",
                        callback_data=f"adjust_{param}"
                    )
                ])
        
        # Help button
        keyboard.append([
            InlineKeyboardButton(
                "❓ Settings Guide",
                callback_data="settings_help"
            )
        ])
        
        # Back button
        keyboard.append([
            InlineKeyboardButton(
                "🔙 Back",
                callback_data="back_to_message"
            )
        ])
        
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def _get_param_icon(param: str) -> str:
        """Get icon for parameter"""
        icons = {
            "temperature": "🌡️",
            "top_p": "🎯",
            "top_k": "🔝",
            "max_tokens": "📝"
        }
        return icons.get(param, "⚙️")

    @staticmethod
    def get_parameter_adjustment_keyboard(param: str, current_value: float, param_info: dict) -> InlineKeyboardMarkup:
        """Get keyboard for parameter adjustment"""
        formatted_value = KeyboardManager.format_param_value(
            current_value,
            param_info["precision"]
        )
        
        keyboard = [
            [
                InlineKeyboardButton("➖", callback_data=f"dec_{param}"),
                InlineKeyboardButton(formatted_value, callback_data=f"current_{param}"),
                InlineKeyboardButton("➕", callback_data=f"inc_{param}")
            ],
            [
                InlineKeyboardButton(
                    f"Range: {param_info['min']} - {param_info['max']} | Step: {param_info['step']}",
                    callback_data=f"info_{param}"
                )
            ],
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="back_to_settings")]
        ]
        
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_settings_help_keyboard() -> InlineKeyboardMarkup:
        """Get keyboard for settings help"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Settings", callback_data="back_to_settings")]
        ])

    @staticmethod
    def get_confirmation_keyboard(action: str, chat_id: int) -> InlineKeyboardMarkup:
        """Get keyboard for confirmation dialogs"""
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ Yes",
                    callback_data=f"confirm_{action}:{chat_id}"
                ),
                InlineKeyboardButton(
                    "❌ No",
                    callback_data=f"cancel_{action}:{chat_id}"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_general_back_keyboard(callback_data: str) -> InlineKeyboardMarkup:
        """Get a general back button keyboard"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data=callback_data)]
        ])

    @staticmethod
    def get_export_format_keyboard(chat_id: int) -> InlineKeyboardMarkup:
        """Get keyboard for selecting export format"""
        keyboard = [
            [
                InlineKeyboardButton(
                    "📄 PDF",
                    callback_data=f"export_format:{chat_id}:pdf"
                ),
                InlineKeyboardButton(
                    "📝 TXT",
                    callback_data=f"export_format:{chat_id}:txt"
                ),
            ],
            [
                InlineKeyboardButton(
                    "📎 DOCX",
                    callback_data=f"export_format:{chat_id}:docx"
                ),
                InlineKeyboardButton(
                    "🗒️ Markdown",
                    callback_data=f"export_format:{chat_id}:md"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data=f"manage_chat:{chat_id}"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def get_language_selection_keyboard(chat_id:int) -> InlineKeyboardMarkup:
        """Get keyboard for language selection"""
        keyboard = []
        for lang_code, lang_info in SUPPORTED_LANGUAGES.items():
            keyboard.append([
                InlineKeyboardButton(
                    f"{lang_info['name']} ({lang_code})",
                    callback_data=f"select_lang:{chat_id}:{lang_code}"
                )
            ])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"manage_chat:{chat_id}")])
        return InlineKeyboardMarkup(keyboard)
