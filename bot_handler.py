# bot_handler.py
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, ForceReply
)

from config import SUPPORTED_LANGUAGES

from pyrogram.errors import (
    MessageNotModified, FloodWait, MessageTooLong, MessageEmpty,
    ChatWriteForbidden, BadRequest
)

import html

from pyrogram.errors import MessageNotModified
from typing import Optional, Union, Dict, Any
import os
import asyncio
from datetime import datetime
import logging
from PIL import Image
import os
import time
import re
from typing import List
from config import (
    API_ID, API_HASH, BOT_TOKEN,
    GEMINI_API_KEY, CLAUDE_API_KEY, DEEPSEEK_API_KEY,
    MODELS, DEFAULT_PARAMS, PARAMETER_CONFIG
)

from tts_handler import GeminiTTS
    

from database import DatabaseManager
from model_manager import ModelManager
from keyboard_manager import KeyboardManager
from export_manager import ExportManager
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


import html
from pyrogram.errors import MessageNotModified
from typing import Optional, Union, Dict, Any
import os
import asyncio
from datetime import datetime
import logging
from PIL import Image
import os
import time
import re
from typing import List
from pyrogram.errors import MessageTooLong
from pyrogram.errors import BadRequest

logger = logging.getLogger(__name__)

class MessageHandler:
    """Utility class for handling message operations"""
    
    def __init__(self):
        self.flood_wait_delays = {}
        self.max_message_length = 4096
        self.sent_chunks = {}
        self.chunk_buffers = {}  # Store buffers for each chunk
        self.temp_states = {}  # Store temporary states of messages

    def format_content(self, text: str, content_type: str = "text") -> str:
        """Format content for better readability"""
        if not text:
            return ""
            
        # Remove unnecessary asterisks at the beginning of lines
        lines = text.split('\n')
        formatted_lines = []
        for line in lines:
            line = line.strip()
            # Only format if line actually starts with bullet point markers
            if line.startswith(('• ', '* ', '- ')) and not line.startswith('```'):
                formatted_lines.append(f"• {line[2:].strip()}")
            else:
                formatted_lines.append(line)
        
        formatted_text = '\n'.join(formatted_lines)
        
        # Add type indicator emoji only if there's a specific content type
        if content_type != "text":
            type_indicators = {
                "image": "🖼️",
                "video": "🎥",
                "audio": "🎵",
                "document": "📄"
            }
            indicator = type_indicators.get(content_type, "")
            if indicator:
                formatted_text = f"{indicator} {formatted_text}"
        
        return formatted_text
    
    def _store_message_state(self, message_id: str, chunks: List[str], original_markup=None):
        """Store message state for later restoration"""
        self.temp_states[message_id] = {
            "chunks": chunks,
            "markup": original_markup
        }
    
    def _get_message_state(self, message_id: str) -> Optional[Dict]:
        """Get stored message state"""
        return self.temp_states.get(message_id)
    
    def _format_code_blocks(self, text: str) -> str:
        """Format code blocks with proper syntax highlighting"""
        lines = text.split('\n')
        in_code_block = False
        formatted_lines = []
        
        for line in lines:
            if line.strip().startswith('```'):
                if not in_code_block:
                    # Start of code block
                    lang = line.strip()[3:] or 'text'
                    formatted_lines.append(f"<pre><code class='language-{lang}'>")
                    in_code_block = True
                else:
                    # End of code block
                    formatted_lines.append("</code></pre>")
                    in_code_block = False
            else:
                if in_code_block:
                    # Inside code block, preserve spaces
                    formatted_lines.append(html.escape(line))
                else:
                    # Outside code block, normal formatting
                    formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def _format_lists(self, text: str) -> str:
        """Format lists with proper indentation and bullets"""
        lines = text.split('\n')
        formatted_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(('•', '-', '*')):
                # Bullet list item
                formatted_lines.append(f"• {stripped[1:].strip()}")
            elif stripped.startswith(('\d+\.', '\d+\)')):
                # Numbered list item
                formatted_lines.append(line)
            else:
                formatted_lines.append(line)
        
        return '\n'.join(formatted_lines)
    
    def _add_spacing(self, text: str) -> str:
        """Add proper spacing between sections"""
        # Add spacing after headings
        text = re.sub(r'(#+.*?)\n', r'\1\n\n', text)
        
        # Add spacing between paragraphs
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Ensure code blocks have spacing
        text = re.sub(r'(</code></pre>)\n?([^\n])', r'\1\n\n\2', text)
        
        return text.strip()
    
    def _clean_and_validate_html(self, text: str) -> str:
        """Clean and validate HTML tags"""
        try:
            # Handle code blocks first
            text = re.sub(
                r'```(\w+)?\n(.*?)\n```',
                lambda m: f'<pre><code class="language-{m.group(1) or "text"}">{html.escape(m.group(2))}</code></pre>',
                text,
                flags=re.DOTALL
            )
            
            # Handle inline code
            text = re.sub(
                r'`([^`]+)`',
                lambda m: f'<code>{html.escape(m.group(1))}</code>',
                text
            )
            
            # Track open tags
            open_tags = []
            result = []
            current_tag = ""
            in_tag = False
            
            for char in text:
                if char == '<':
                    in_tag = True
                    current_tag = char
                elif char == '>' and in_tag:
                    current_tag += char
                    tag_match = re.match(r'</?([a-z0-9]+)', current_tag.lower())
                    
                    if tag_match:
                        tag_name = tag_match.group(1)
                        if current_tag.startswith('</'):
                            if open_tags and open_tags[-1] == tag_name:
                                open_tags.pop()
                                result.append(current_tag)
                            else:
                                # Invalid closing tag - escape it
                                result.append(html.escape(current_tag))
                        else:
                            open_tags.append(tag_name)
                            result.append(current_tag)
                    else:
                        # Invalid tag - escape it
                        result.append(html.escape(current_tag))
                        
                    in_tag = False
                    current_tag = ""
                elif in_tag:
                    current_tag += char
                else:
                    result.append(char)
            
            # If we have an unclosed tag at the end
            if current_tag:
                result.append(html.escape(current_tag))
                
            # Close any remaining open tags
            for tag in reversed(open_tags):
                result.append(f'</{tag}>')
            
            return ''.join(result)
            
        except Exception as e:
            logger.error(f"Error in HTML cleaning: {str(e)}")
            # Fall back to escaping all HTML
            return html.escape(text)

    async def edit_message_safely(self, message, text: str, reply_markup=None, content_type: str = "text", max_retries=3):
        """Safely edit a message with proper error handling and formatting"""
        try:
            message_id = str(message.id)
            formatted_text = self.format_content(text, content_type)
            
            # Clean and validate HTML
            formatted_text = self._clean_and_validate_html(formatted_text)
            
            # Check if we need to split the message
            if len(formatted_text) > self.max_message_length:
                chunks = self._split_message(formatted_text)
                
                # Store the state
                self._store_message_state(message_id, chunks, reply_markup)
                
                # If we already have chunk messages
                if message_id in self.sent_chunks:
                    existing_messages = self.sent_chunks[message_id]
                    
                    # If we need more messages
                    while len(existing_messages) < len(chunks):
                        chunk_msg = await message.reply_text("")
                        existing_messages.append(chunk_msg)
                    
                    # If we have too many messages
                    while len(existing_messages) > len(chunks):
                        msg_to_delete = existing_messages.pop()
                        try:
                            await msg_to_delete.delete()
                        except Exception as e:
                            logger.error(f"Error deleting excess message: {str(e)}")
                    
                    # Update all chunks
                    for i, (chunk, msg) in enumerate(zip(chunks, existing_messages)):
                        try:
                            await msg.edit_text(
                                chunk,
                                reply_markup=reply_markup if i == len(chunks)-1 else None
                            )
                        except MessageNotModified:
                            continue
                else:
                    # First time sending chunks
                    sent_messages = []
                    
                    # Edit first message
                    try:
                        await message.edit_text(
                            chunks[0],
                            reply_markup=None
                        )
                        sent_messages.append(message)
                    except Exception as e:
                       logger.error(f"Error editing first message: {str(e)}")
                       return
                    
                    # Send remaining chunks
                    for i, chunk in enumerate(chunks[1:]):
                        try:
                           sent_msg = await message.reply_text(chunk)
                           sent_messages.append(sent_msg)
                        except Exception as e:
                            logger.error(f"Error sending message chunk: {str(e)}")
                            continue
                        await asyncio.sleep(0.1)  # Add a delay between sending chunks

                    # Add markup to last message
                    if reply_markup:
                        try:
                            await sent_messages[-1].edit_reply_markup(reply_markup)
                        except Exception as e:
                            logger.error(f"Error adding reply markup: {str(e)}")
                    
                    self.sent_chunks[message_id] = sent_messages
            else:
                # For normal length messages
                await message.edit_text(
                    formatted_text,
                    reply_markup=reply_markup
                )
        
        except FloodWait as e:
            await asyncio.sleep(e.value)
            if max_retries > 0:
                return await self.edit_message_safely(
                    message, text, reply_markup, content_type, max_retries - 1
                )
        except MessageNotModified:
            pass
        except MessageTooLong:
             logger.warning(f"MessageTooLong error for message id: {message.id}, splitting message...")

             # delete old messages if exists
             await self.delete_message_chunks(message_id)

             # Split the message and send it again
             chunks = self._split_message(formatted_text)

             # Store the state
             self._store_message_state(message_id, chunks, reply_markup)

             # Delete original message
             try:
                 await message.delete()
             except Exception as e:
                 logger.error(f"Error deleting original message: {str(e)}")
                 return  # skip if deleting original message failed

             # Send remaining chunks
             sent_messages = []
             
             # Edit first message
             try:
                 sent_messages.append(message)
                 await message.edit_text(
                     chunks[0],
                     reply_markup=None
                 )
             except Exception as e:
                 logger.error(f"Error editing first message: {str(e)}")
                 return
             
             # Send remaining chunks
             for i, chunk in enumerate(chunks[1:]):
                 try:
                     sent_msg = await message.reply_text(chunk)
                     sent_messages.append(sent_msg)
                 except Exception as e:
                     logger.error(f"Error sending message chunk: {str(e)}")
                     continue
                 await asyncio.sleep(0.1) # Add a delay between sending chunks

             # Add markup to last message
             if reply_markup:
                try:
                    await sent_messages[-1].edit_reply_markup(reply_markup)
                except Exception as e:
                   logger.error(f"Error adding reply markup: {str(e)}")

             self.sent_chunks[message_id] = sent_messages
        except BadRequest as e:
              logger.error(f"BadRequest error while editing message: {str(e)}")
              # Handle BadRequest (e.g., if message is deleted)
              try:
                 await message.delete() # Try to delete the message to prevent further errors
              except Exception as delete_e:
                 logger.error(f"Error deleting message after BadRequest error: {str(delete_e)}")
        except Exception as e:
            logger.error(f"Error editing message: {str(e)}")

    async def restore_messages(self, message_id: str, first_message):
        """Restore multiple messages to their previous state"""
        state = self._get_message_state(message_id)
        if not state:
            return
            
        chunks = state["chunks"]
        markup = state["markup"]
        
        if message_id in self.sent_chunks:
            sent_messages = self.sent_chunks[message_id]
            
            # Restore all chunks
            for i, (chunk, msg) in enumerate(zip(chunks, sent_messages)):
                try:
                    if i == 0 and msg.id == first_message.id:
                        await msg.edit_text(
                            chunk,
                            reply_markup=None
                        )
                    else:
                        # For chunks that might have been hidden/deleted, send new messages
                        new_msg = await first_message.reply_text(chunk)
                        sent_messages[i] = new_msg
                except Exception as e:
                    logger.error(f"Error restoring chunk {i}: {str(e)}")
            
            # Add markup to last message
            if markup and sent_messages:
                try:
                    await sent_messages[-1].edit_reply_markup(markup)
                except Exception as e:
                    logger.error(f"Error restoring markup: {str(e)}")
    
    async def delete_message_chunks(self, message_id: str):
        """Delete all chunks associated with a message"""
        if message_id in self.sent_chunks:
            for msg in self.sent_chunks[message_id][1:]:  # Skip first message
                try:
                    await msg.delete()
                except Exception as e:
                    logger.error(f"Error deleting message chunk: {str(e)}")
            del self.sent_chunks[message_id]

    def _split_message(self, text: str) -> List[str]:
        """Split long message into chunks"""
        chunks = []
        current_chunk = ""
        in_code_block = False
        code_buffer = []
        
        for line in text.split('\n'):
            # Handle code blocks specially
            if line.startswith('```') or line.startswith('<pre>'):
                in_code_block = not in_code_block
                code_buffer.append(line)
                if not in_code_block:  # End of code block
                    code_text = '\n'.join(code_buffer)
                    if len(current_chunk) + len(code_text) + 1 > self.max_message_length:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        chunks.append(code_text.strip())
                        current_chunk = ""
                    else:
                        current_chunk += ('\n' + code_text if current_chunk else code_text)
                    code_buffer = []
                continue
            elif in_code_block:
                code_buffer.append(line)
                continue
                
            # Handle regular text
            if len(current_chunk) + len(line) + 1 > self.max_message_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += ('\n' + line if current_chunk else line)
        
        # Add remaining text
        if code_buffer:  # Handle any remaining code block
            code_text = '\n'.join(code_buffer)
            if len(current_chunk) + len(code_text) + 1 > self.max_message_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                chunks.append(code_text.strip())
            else:
                current_chunk += ('\n' + code_text if current_chunk else code_text)
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text"""
        clean_text = re.sub(r'<[^>]+>', '', text)
        return clean_text.strip()

    async def restore_messages(self, message_id: str, first_message):
        """Restore multiple messages to their previous state"""
        state = self._get_message_state(message_id)
        if not state:
            return
            
        chunks = state["chunks"]
        markup = state["markup"]
        
        if message_id in self.sent_chunks:
            sent_messages = self.sent_chunks[message_id]
            
            # Restore all chunks
            for i, (chunk, msg) in enumerate(zip(chunks, sent_messages)):
                try:
                    if i == 0 and msg.id == first_message.id:
                        await msg.edit_text(
                            chunk,
                            reply_markup=None
                        )
                    else:
                        # For chunks that might have been hidden/deleted, send new messages
                        new_msg = await first_message.reply_text(chunk)
                        sent_messages[i] = new_msg
                except Exception as e:
                    logger.error(f"Error restoring chunk {i}: {str(e)}")
            
            # Add markup to last message
            if markup and sent_messages:
                try:
                    await sent_messages[-1].edit_reply_markup(markup)
                except Exception as e:
                    logger.error(f"Error restoring markup: {str(e)}")
    
    async def delete_message_chunks(self, message_id: str):
        """Delete all chunks associated with a message"""
        if message_id in self.sent_chunks:
            for msg in self.sent_chunks[message_id][1:]:  # Skip first message
                try:
                    await msg.delete()
                except Exception as e:
                    logger.error(f"Error deleting message chunk: {str(e)}")
            del self.sent_chunks[message_id]

    def _split_message(self, text: str) -> List[str]:
        """Split long message into chunks"""
        chunks = []
        current_chunk = ""
        in_code_block = False
        code_buffer = []
        
        for line in text.split('\n'):
            # Handle code blocks specially
            if line.startswith('```') or line.startswith('<pre>'):
                in_code_block = not in_code_block
                code_buffer.append(line)
                if not in_code_block:  # End of code block
                    code_text = '\n'.join(code_buffer)
                    if len(current_chunk) + len(code_text) + 1 > self.max_message_length:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        chunks.append(code_text.strip())
                        current_chunk = ""
                    else:
                        current_chunk += ('\n' + code_text if current_chunk else code_text)
                    code_buffer = []
                continue
            elif in_code_block:
                code_buffer.append(line)
                continue
                
            # Handle regular text
            if len(current_chunk) + len(line) + 1 > self.max_message_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += ('\n' + line if current_chunk else line)
        
        # Add remaining text
        if code_buffer:  # Handle any remaining code block
            code_text = '\n'.join(code_buffer)
            if len(current_chunk) + len(code_text) + 1 > self.max_message_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                chunks.append(code_text.strip())
            else:
                current_chunk += ('\n' + code_text if current_chunk else code_text)
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text"""
        clean_text = re.sub(r'<[^>]+>', '', text)
        return clean_text.strip()

class AIBot:
    def __init__(self):
        """Initialize bot with necessary configurations"""
        # Initialize Pyrogram client
        self.app = Client(
            "ai_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )
        
        # Initialize managers
        self.db = DatabaseManager("ai_chat.db")
        self.model_manager = ModelManager(
            gemini_api_key=GEMINI_API_KEY,
            claude_api_key=CLAUDE_API_KEY,
            deepseek_api_key=DEEPSEEK_API_KEY
        )
        self.keyboard_manager = KeyboardManager()
        self.export_manager = ExportManager()

        # Initialize state tracking
        self.user_states = {}  # Track user states
        self.active_chats = {}  # Track active chats per user
        self.temp_data = {}  # Temporary data storage
        self.rename_states = {}  # Track users in rename mode
        self.temp_files = {}  # Track temporary files
        self.message_contents = {}  # Track message contents for settings


        # Create temp directory if it doesn't exist
        os.makedirs("temp", exist_ok=True)

        # Register handlers
        self._register_handlers()

        self.message_handler = MessageHandler()

        self.tts_handler = GeminiTTS()

    def _register_handlers(self):
        """Register all message and callback handlers"""
        
        # Command handlers
        @self.app.on_message(filters.command(["start", "help"]))
        async def start_command(client, message):
            await self.handle_start(message)

        @self.app.on_message(filters.command("settings"))
        async def settings_command(client, message):
            await self.handle_settings(message)

        @self.app.on_message(filters.command("cancel"))
        async def cancel_command(client, message):
            await self.handle_cancel(message)

        # Message handlers
        @self.app.on_message(filters.private & ~filters.command("*"))
        async def message_handler(client, message):
            if message.text:
                if message.from_user.id in self.rename_states:
                    await self.handle_rename_input(message)
                else:
                    await self.handle_text_message(message)
            elif message.photo:
                await self.handle_photo_message(message)
            elif message.video:
                await self.handle_video_message(message)
            elif message.audio or message.voice:
                await self.handle_audio_message(message)
            elif message.document:
                await self.handle_document_message(message)

        # Callback query handler
        @self.app.on_callback_query()
        async def callback_handler(client, callback_query):
            await self.handle_callback(callback_query)

    async def handle_start(self, message: Message):
        """Handle /start command"""
        user_id = message.from_user.id
        
        # Create or get user in database
        self.db.get_or_create_user(user_id)
        
        # Reset user state
        self.user_states[user_id] = "selecting_model"
        
        welcome_text = (
            "👋 Welcome to AI Assistant Bot!\n\n"
            "I support multiple AI models that can help you with various tasks:\n\n"
            "✨ <b>Google Gemini</b>\n"
            "• Latest versions (1.5 Flash, 1.5 Pro, 2.0)\n"
            "• Supports text, images, video, and audio\n\n"
            "🧠 <b>Anthropic Claude</b>\n"
            "• Latest versions (3.5 Haiku and Sonnet)\n"
            "• Supports text and images\n\n"
            "🐳 <b>DeepSeek</b>\n"
            "• Latest version (V3)\n"
            "• Specializes in text processing\n\n"
            "Please select a model to begin:"
        )
        
        await message.reply_text(
            welcome_text,
            parse_mode=ParseMode.HTML,
            reply_markup=self.keyboard_manager.get_model_selection_keyboard()
        )

    async def handle_callback(self, callback_query: CallbackQuery):
            """Main callback query handler"""
            try:
                data = callback_query.data
                user_id = callback_query.from_user.id

                logger.info(f"Received callback data: {data} from user {user_id}")
    
                # Check if it's a parameter adjustment callback
                if any(data.startswith(prefix) for prefix in ["adjust_", "inc_", "dec_"]) \
                or data in ["settings:advanced", "settings_help", "back_to_settings"]:
                    await self.handle_settings_callback(callback_query)
                    return

                # Model selection handlers
                if data.startswith("select_model:"):
                    await self.handle_model_selection(callback_query)

                elif data.startswith("select_version:"):
                    await self.handle_version_selection(callback_query)

                # Chat management handlers
                elif data in ["new_chat", "select_chat"]:
                    await self.handle_chat_management(callback_query)

                elif data.startswith("select_chat:"):
                    await self.handle_chat_selection(callback_query)

                elif data.startswith("manage_chat:"):
                    await self.handle_chat_management_options(callback_query)

                elif data.startswith("rename_chat:"):
                    await self.handle_rename_chat(callback_query)

                elif data.startswith("delete_chat:"):
                    await self.handle_delete_chat(callback_query)

                elif data.startswith("confirm_delete:"):
                    await self.handle_confirm_delete_chat(callback_query)

                elif data.startswith("cancel_delete:"):
                    await self.handle_cancel_delete_chat(callback_query)

                # Model settings handlers
                elif data == "model_settings":
                    await self.handle_model_settings(callback_query)

                elif data == "change_model":
                    await self.handle_change_model(callback_query)

                # Navigation handlers
                elif data == "back_to_models":
                    await self.handle_back_to_models(callback_query)

                elif data == "back_to_options":
                    await self.handle_back_to_options(callback_query)

                elif data == "back_to_message":
                    await self.handle_back_to_message(callback_query)

                elif data == "back_to_chats":
                    await self.handle_back_to_chats(callback_query)

                elif data.startswith("export_chat:"):
                    await self.handle_export_chat(callback_query)

                elif data.startswith("export_format:"):
                    await self.handle_export_format(callback_query)

                # Regeneration handler
                elif data.startswith("regenerate:"):
                    await self.handle_regeneration(callback_query)
                elif data.startswith("change_lang:"):
                    await self.handle_change_lang(callback_query)
                elif data.startswith("select_lang:"):
                    await self.handle_select_lang(callback_query)

                else:
                    logger.warning(f"Unhandled callback data: {data}")
                    await callback_query.answer("Unknown callback")

            except Exception as e:
                logger.error(f"Error in callback handler: {str(e)}", exc_info=True)
                await callback_query.answer(
                    "❌ An error occurred. Please try again.",
                    show_alert=True
                )

    async def handle_settings_help(self, callback_query: CallbackQuery):
        """Handle settings help button"""
        help_text = (
            "📚 <b>Settings Guide</b>\n\n"
            "<b>Temperature (Creativity)</b>\n"
            "Controls how creative or focused the responses are.\n"
            "• Lower = more focused and precise\n"
            "• Higher = more creative and varied\n\n"
            "<b>Top P (Diversity)</b>\n"
            "Controls how varied the word choices are.\n"
            "• Lower = more conservative choices\n"
            "• Higher = more diverse vocabulary\n\n"
            "<b>Top K (Range)</b>\n"
            "Limits the vocabulary range.\n"
            "• Lower = strict vocabulary\n"
            "• Higher = broader word selection\n\n"
            "<b>Max Tokens (Length)</b>\n"
            "Sets maximum response length.\n"
            "• Lower = shorter responses\n"
            "• Higher = longer, detailed responses"
        )
        
        await callback_query.message.edit_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=self.keyboard_manager.get_settings_help_keyboard()
        )

    async def handle_back_to_settings(self, callback_query: CallbackQuery):
        """Handle back to settings button"""
        user_id = callback_query.from_user.id
        model, version, current_params = self.db.get_user_settings(user_id)
        
        settings_text = (
            "🛠️ <b>Advanced Settings</b>\n\n"
            f"Current settings for {model.upper()}:\n\n"
        )
        
        for param, value in current_params.items():
            if param in PARAMETER_CONFIG:
                precision = PARAMETER_CONFIG[param]["precision"]
                formatted_value = round(float(value), precision) if precision > 0 else int(float(value))
                settings_text += f"• <b>{param.replace('_', ' ').title()}:</b> {formatted_value}\n"
        
        settings_text += "\nClick on any parameter to adjust it."
        
        await callback_query.message.edit_text(
            settings_text,
            parse_mode=ParseMode.HTML,
            reply_markup=self.keyboard_manager.get_settings_keyboard(
                model=model,
                current_params=current_params
            )
        )

    async def handle_cancel_delete_chat(self, callback_query: CallbackQuery):
        """Handle cancellation of chat deletion"""
        chat_id = int(callback_query.data.split(":")[1])
        
        # Show chat management options again
        await callback_query.message.edit_text(
            "What would you like to do with this chat?",
            reply_markup=self.keyboard_manager.get_chat_management_keyboard(chat_id)
        )

    async def handle_back_to_chats(self, callback_query: CallbackQuery):
        """Handle back to chats button"""
        user_id = callback_query.from_user.id
        chats = self.db.get_user_chats(user_id)
        
        if chats:
            await callback_query.message.edit_text(
                "Select a chat to continue:",
                reply_markup=self.keyboard_manager.get_chat_list_keyboard(chats)
            )
        else:
            await callback_query.message.edit_text(
                "You don't have any chats yet.",
                reply_markup=self.keyboard_manager.get_chat_options_keyboard()
            )   
    async def handle_model_selection(self, callback_query: CallbackQuery):
        """Handle model selection callback"""
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        model = data.split(":")[1]
        self.temp_data[user_id] = {"selected_model": model}
        
        # Get available versions for the selected model
        versions = MODELS[model]["versions"]
        
        await callback_query.message.edit_text(
            f"Select the version of {model} you want to use:",
            reply_markup=self.keyboard_manager.get_model_version_keyboard(model, versions)
        )

    async def handle_version_selection(self, callback_query: CallbackQuery):
        """Handle model version selection callback"""
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        _, model, version = data.split(":")
        
        # Update user settings in database
        self.db.update_user_model(user_id, model, version)
        
        # Clear temporary data
        if user_id in self.temp_data:
            del self.temp_data[user_id]
        
        # Show chat options
        await callback_query.message.edit_text(
            f"✅ Model set to {model} ({version})\n\n"
            "What would you like to do?",
            reply_markup=self.keyboard_manager.get_chat_options_keyboard()
        )

    async def handle_chat_management(self, callback_query: CallbackQuery):
        """Handle chat management callbacks"""
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if data == "new_chat":
            model, version, _ = self.db.get_user_settings(user_id)
            chat_id = self.db.create_chat(
                user_id=user_id,
                title=f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                model=model,
                version=version
            )

            # Set default language for the new chat
            self.db.update_chat_lang_code(chat_id, "en-US")
            
            # Set as active chat
            self.active_chats[user_id] = chat_id
            
            await callback_query.message.edit_text(
                "🆕 New chat created!\n\n"
                "You can now:\n"
                "• Send text messages\n"
                "• Send images (Gemini and Claude)\n"
                "• Send videos (Gemini only)\n"
                "• Send audio (Gemini only)\n"
                "• Send documents for analysis(Gemini and Claude)\n\n"
                "Send your first message to begin!",
                reply_markup=self.keyboard_manager.get_message_actions_keyboard(0)
            )
        
        
        elif data == "select_chat":
            chats = self.db.get_user_chats(user_id)
            if not chats:
                await callback_query.answer(
                    "You don't have any previous chats. Start a new one!",
                    show_alert=True
                )
                return
                     
            await callback_query.message.edit_text(
                "Select a chat to continue:",
                reply_markup=self.keyboard_manager.get_chat_list_keyboard(chats)
            )

    async def handle_change_lang(self, callback_query: CallbackQuery):
            """Handle language change request"""
            chat_id = int(callback_query.data.split(":")[1])
            await callback_query.message.edit_text(
                "Select language:",
                reply_markup=self.keyboard_manager.get_language_selection_keyboard(chat_id)
            )

    async def handle_select_lang(self, callback_query: CallbackQuery):
        """Handle language selection"""
        _, chat_id, lang_code = callback_query.data.split(":")
        chat_id = int(chat_id)

        success = self.db.update_chat_lang_code(chat_id, lang_code)
        if success:
            await callback_query.message.edit_text(
                f"✅ Language set to {SUPPORTED_LANGUAGES[lang_code]['name']}",
                 reply_markup=self.keyboard_manager.get_chat_management_keyboard(chat_id)
            )
        else:
           await callback_query.message.edit_text(
                "❌ Failed to change language.",
                reply_markup=self.keyboard_manager.get_chat_management_keyboard(chat_id)
            )

    async def handle_chat_selection(self, callback_query: CallbackQuery):
        """Handle chat selection"""
        chat_id = int(callback_query.data.split(":")[1])
        user_id = callback_query.from_user.id
        
        # Set as active chat
        self.active_chats[user_id] = chat_id
        
        # Get all messages from this chat
        messages = self.db.get_chat_history(chat_id)
        
        if messages:
            # Show last few messages for context
            last_messages = messages[-3:]  # Get last 3 messages
            context_text = "Recent messages in this chat:\n\n"
            
            for msg in last_messages:
                role_icon = "👤" if msg["role"] == "user" else "🤖"
                content_preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                context_text += f"{role_icon} {content_preview}\n\n"
            
            context_text += "You can continue the conversation..."
            
            await callback_query.message.edit_text(
                context_text,
                reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                    last_messages[-1]['telegram_message_id'] if last_messages else 0
                )
            )
        else:
            await callback_query.message.edit_text(
                "Chat selected. Send a message to begin!",
                reply_markup=self.keyboard_manager.get_message_actions_keyboard(0)
            )

    async def handle_chat_management_options(self, callback_query: CallbackQuery):
        """Handle chat management options"""
        chat_id = int(callback_query.data.split(":")[1])
        
        await callback_query.message.edit_text(
            "What would you like to do with this chat?",
            reply_markup=self.keyboard_manager.get_chat_management_keyboard(chat_id)
        )

    async def handle_rename_chat(self, callback_query: CallbackQuery):
        """Handle chat rename initiation"""
        chat_id = int(callback_query.data.split(":")[1])
        user_id = callback_query.from_user.id
        
        # Set user in rename mode
        self.rename_states[user_id] = chat_id
        
        await callback_query.message.edit_text(
            "Please send the new title for this chat:",
            reply_markup=self.keyboard_manager.get_general_back_keyboard("back_to_chats")
        )

    async def handle_rename_input(self, message: Message):
        """Handle chat rename input"""
        user_id = message.from_user.id
        chat_id = self.rename_states.get(user_id)
        
        if not chat_id:
            return
        
        new_title = message.text.strip()
        if len(new_title) > 100:
            await message.reply_text(
                "❌ Title too long. Please use a shorter title (max 100 characters)."
            )
            return
        
        success = self.db.update_chat_title(chat_id, new_title)
        if success:
            del self.rename_states[user_id]
            
            # Show updated chat list
            chats = self.db.get_user_chats(user_id)
            await message.reply_text(
                "✅ Chat renamed successfully!",
                reply_markup=self.keyboard_manager.get_chat_list_keyboard(chats)
            )
        else:
            await message.reply_text(
                "❌ Failed to rename chat. Please try again.",
                reply_markup=self.keyboard_manager.get_chat_management_keyboard(chat_id)
            )

    async def handle_delete_chat(self, callback_query: CallbackQuery):
        """Handle chat deletion confirmation"""
        chat_id = int(callback_query.data.split(":")[1])
        
        await callback_query.message.edit_text(
            "⚠️ Are you sure you want to delete this chat? This action cannot be undone.",
            reply_markup=self.keyboard_manager.get_confirmation_keyboard("delete", chat_id)
        )

    async def handle_confirm_delete_chat(self, callback_query: CallbackQuery):
        """Handle chat deletion confirmation"""
        chat_id = int(callback_query.data.split(":")[1])
        user_id = callback_query.from_user.id
        
        success = self.db.delete_chat(chat_id)
        if success:
            if self.active_chats.get(user_id) == chat_id:
                self.active_chats.pop(user_id)
            
            # Show updated chat list
            chats = self.db.get_user_chats(user_id)
            if chats:
                await callback_query.message.edit_text(
                    "Chat deleted successfully!",
                    reply_markup=self.keyboard_manager.get_chat_list_keyboard(chats)
                )
            else:
                await callback_query.message.edit_text(
                    "Chat deleted. You have no active chats.",
                    reply_markup=self.keyboard_manager.get_chat_options_keyboard()
                )
        else:
            await callback_query.answer(
                "Failed to delete chat. Please try again.",
                show_alert=True
            )
    
    async def handle_other_callbacks(self, callback_query: CallbackQuery):
        """Handle other callback queries"""
        data = callback_query.data
        if data.startswith("adjust_"):
            await self.handle_settings_callback(callback_query)
        else:
            await callback_query.answer("Unknown callback")

    async def handle_back_to_message(self, callback_query: CallbackQuery):
        """Handle back to message button"""
        try:
            message_id = callback_query.message.id
            original_message = await self._get_original_message(message_id)
            if original_message:
                await callback_query.message.edit_text(
                    original_message["content"],
                    reply_markup=self.keyboard_manager.get_message_actions_keyboard(message_id)
                )
            else:
                user_id = callback_query.from_user.id
                model, version, _ = self.db.get_user_settings(user_id)
                await callback_query.message.edit_text(
                    f"Using {model} ({version}). Send a message to begin!",
                    reply_markup=self.keyboard_manager.get_message_actions_keyboard(0)
                )
        except Exception as e:
            logger.error(f"Error in back to message: {str(e)}")
            await callback_query.answer("Error returning to message", show_alert=True)

    async def handle_back_to_models(self, callback_query: CallbackQuery):
        """Handle back to models button"""
        await callback_query.message.edit_text(
            "Select a model:",
            reply_markup=self.keyboard_manager.get_model_selection_keyboard()
        )

    async def handle_back_to_options(self, callback_query: CallbackQuery):
        """Handle back to options button"""
        message = callback_query.message
        message_id = str(message.id)
        
        try:
            # If this is a multi-message response
            if message_id in self.message_handler.sent_chunks:
                await self.message_handler.restore_messages(
                    message_id,
                    message
                )
            else:
                # For single messages
                await message.edit_reply_markup(
                    reply_markup=self.keyboard_manager.get_chat_options_keyboard()
                )
        except Exception as e:
            logger.error(f"Error in back to options: {str(e)}")
            await callback_query.answer(
                "❌ Error returning to previous menu.",
                show_alert=True
            )


    async def handle_text_message(self, message: Message):
        """Handle incoming text messages"""
        user_id = message.from_user.id

        # Validate user settings
        model, version, params = self.db.get_user_settings(user_id)
        if not model or not version:
            await message.reply_text(
                "⚠️ Please select a model first using /start",
                reply_markup=self.keyboard_manager.get_model_selection_keyboard()
            )
            return

        # Check active chat
        if user_id not in self.active_chats:
            await message.reply_text(
                "Please start a new chat or select an existing one:",
                reply_markup=self.keyboard_manager.get_chat_options_keyboard()
            )
            return

        try:
            # Send initial "thinking" message
            status_message = await message.reply_text(
                "🤔 Thinking...",
                reply_to_message_id=message.id
            )

            # Get chat history
            chat_history = self.db.get_chat_history(self.active_chats[user_id])
            formatted_history = []
            for msg in chat_history:
                formatted_history.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "content_type": msg.get("content_type", "text")
                })

            # Process with model
            response_text = ""
            async for chunk in self.model_manager.process_content(
                model_name=model,
                model_version=version,
                content=message.text,
                content_type="text",
                chat_history=formatted_history,  # Add chat history
                **params
            ):
                response_text += chunk
                try:
                    await status_message.edit_text(
                        response_text,
                        reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                            status_message.id
                        )
                    )
                except MessageNotModified:
                    continue

            # Save messages to database
            self.db.add_message(
                chat_id=self.active_chats[user_id],
                role="user",
                content=message.text,
                telegram_message_id=message.id
            )

            self.db.add_message(
                chat_id=self.active_chats[user_id],
                role="assistant",
                content=response_text,
                telegram_message_id=status_message.id,
                model_params=params
            )

            # Get language code from database
            chat_info = self.db.get_chat_info(self.active_chats[user_id])
            lang_code = 'en-US'  # Default language
            if chat_info:
               lang_code = chat_info.get('lang_code', 'en-US')

            # Check message length before sending
            if len(response_text) > self.message_handler.max_message_length:
                chunks = self.message_handler.split_message(response_text)

                #Send message in chunks
                sent_messages = []
                #Edit first message
                await status_message.edit_text(
                    chunks[0],
                    reply_markup=None
                )
                sent_messages.append(status_message)

                # Send remaining chunks
                for chunk in chunks[1:]:
                    sent_msg = await message.reply_text(chunk)
                    sent_messages.append(sent_msg)

                # Add markup to last message
                try:
                    await sent_messages[-1].edit_reply_markup(
                        self.keyboard_manager.get_message_actions_keyboard(
                            status_message.id
                        )
                    )
                except Exception as e:
                    logger.error(f"Error adding reply markup: {str(e)}")
                    
                self.message_handler.sent_chunks[str(status_message.id)] = sent_messages
            else:
                await self.message_handler.edit_message_safely(
                    status_message,
                    response_text,
                    reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                        status_message.id
                    )
                )
            # Send voice message
            await self._send_voice_message(status_message, response_text, lang_code)

        except Exception as e:
            logger.error(f"Error processing text message: {str(e)}")
            error_message = str(e)
            if "API key not valid" in error_message.lower():
                error_message = "Invalid API key. Please contact the bot administrator."
            elif "rate limit" in error_message.lower():
                error_message = "Rate limit exceeded. Please try again later."
            await status_message.edit_text(f"❌ Error: {error_message}")
    

    async def _send_voice_message(self, message: Message, text: str, lang_code: str, delete_previous:bool = False):
        """Convert text to speech and send it as voice message"""
        try:
            status_message = await message.reply_text("🎤 Generating voice message...", reply_to_message_id=message.id)
            
            # delete previous voice messages from message if it exist
            if delete_previous:
                 if hasattr(message, 'reply_to_message') and message.reply_to_message:
                     if hasattr(message.reply_to_message, 'replies'):
                        async for reply_message in message.reply_to_message.iter_replies():
                            if reply_message.voice:
                                try:
                                    await reply_message.delete()
                                except Exception as e:
                                    logger.error(f"Error deleting previous voice message: {e}")
                 elif hasattr(message, 'replies'):
                     async for reply_message in message.iter_replies():
                        if reply_message.voice:
                           try:
                             await reply_message.delete()
                           except Exception as e:
                              logger.error(f"Error deleting previous voice message: {e}")
            
            success = self.tts_handler.text_to_speech(text, lang_code)
            
            if success:
                # get file name for recent file that is saved with this lang code:
                file_name = None
                
                for filename in os.listdir(self.tts_handler.output_dir):
                  if filename.startswith(f"tts_{lang_code}_") and filename.endswith(".mp3"):
                    file_path = self.tts_handler.output_dir / filename
                    if not file_name:
                       file_name = file_path
                    elif os.path.getctime(file_path) > os.path.getctime(file_name):
                        file_name = file_path
                
                if file_name:
                    await message.reply_voice(
                        voice=str(file_name),
                        reply_to_message_id=message.id
                    )
                    await status_message.delete()
                
                    try:
                       os.remove(file_name)
                    except Exception as e:
                       logger.error(f"Error removing audio file: {e}")
                else:
                    await status_message.edit_text("❌ Could not find audio file.")
            else:
                await status_message.edit_text("❌ Could not generate voice message.")
        except Exception as e:
            logger.error(f"Error sending voice message: {e}")
            await status_message.edit_text(f"❌ Error sending voice message: {e}")

    async def handle_photo_message(self, message: Message):
            """Handle photo messages"""
            user_id = message.from_user.id

            # Validate user settings
            model, version, params = self.db.get_user_settings(user_id)
            if not model or not version:
                await message.reply_text("⚠️ Please select a model first using /start")
                return

            if user_id not in self.active_chats:
                await message.reply_text(
                    "Please start a new chat first:",
                    reply_markup=self.keyboard_manager.get_chat_options_keyboard()
                )
                return

            try:
                status_message = await message.reply_text(
                    "🖼️ Processing image...",
                    reply_to_message_id=message.id
                )

                # Download photo
                os.makedirs("temp", exist_ok=True)
                photo_path = os.path.join(
                    "temp",
                    f"{user_id}_{message.id}_photo.jpg"
                )
                await message.download(file_name=photo_path)

                # Store file path for regeneration
                self.temp_files[str(message.id)] = {
                    "path": photo_path,
                    "type": "image"
                }

                # Get chat history
                chat_history = self.db.get_chat_history(self.active_chats[user_id])
                formatted_history = []
                for msg in chat_history:
                    formatted_history.append({
                        "role": msg["role"],
                        "content": msg["content"],
                        "content_type": msg.get("content_type", "text")
                    })

                response_text = ""
                buffer = ""

                async for chunk in self.model_manager.process_content(
                    model_name=model,
                    model_version=version,
                    content=message.caption or "Analyze this image",
                    content_type="image",
                    file_path=photo_path,
                    chat_history=formatted_history,
                    **params
                ):
                    response_text += chunk
                    buffer += chunk

                    # Update message periodically to avoid flood limits
                    if len(buffer) >= 100:
                        await self.message_handler.edit_message_safely(
                            status_message,
                            response_text,
                            reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                                status_message.id
                            )
                        )
                        buffer = ""
                        await asyncio.sleep(0.1)

                # Final update
                if response_text:
                    await self.message_handler.edit_message_safely(
                        status_message,
                        response_text,
                        reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                            status_message.id
                        )
                    )

                # Save to database
                self.db.add_message(
                    chat_id=self.active_chats[user_id],
                    role="user",
                    content=message.caption or "",
                    content_type="image",
                    file_path=photo_path,
                    telegram_message_id=message.id
                )

                self.db.add_message(
                    chat_id=self.active_chats[user_id],
                    role="assistant",
                    content=response_text,
                    telegram_message_id=status_message.id,
                    model_params=params
                )

                # Get language code from database
                chat_info = self.db.get_chat_info(self.active_chats[user_id])
                lang_code = 'en-US'  # Default language
                if chat_info:
                    lang_code = chat_info.get('lang_code', 'en-US')

                 # Send voice message
                await self._send_voice_message(status_message, response_text, lang_code)

            except Exception as e:
                logger.error(f"Error processing photo: {str(e)}")
                await status_message.edit_text(
                    f"❌ Error processing image. Please try again later.",
                    reply_markup=self.keyboard_manager.get_general_back_keyboard("back_to_options")
                )
    
    async def handle_video_message(self, message: Message):
            """Handle video messages"""
            user_id = message.from_user.id

            # Validate user settings
            model, version, params = self.db.get_user_settings(user_id)
            if not model or not version:
                await message.reply_text("⚠️ Please select a model first using /start")
                return

            if "video" not in MODELS[model]["supported_inputs"]:
                await message.reply_text(
                    f"⚠️ The selected model ({model}) doesn't support video input."
                )
                return

            try:
                status_message = await message.reply_text(
                    "🎥 Processing video...",
                    reply_to_message_id=message.id
                )

                # Download video
                os.makedirs("temp", exist_ok=True)
                video_path = os.path.join(
                    "temp",
                    f"{user_id}_{message.id}_video.mp4"
                )
                await message.download(file_name=video_path)

                # Store file path for regeneration
                self.temp_files[str(message.id)] = {
                    "path": video_path,
                    "type": "video"
                }

                # Get chat history
                chat_history = self.db.get_chat_history(self.active_chats[user_id])
                formatted_history = []
                for msg in chat_history:
                    formatted_history.append({
                        "role": msg["role"],
                        "content": msg["content"],
                        "content_type": msg.get("content_type", "text")
                    })

                response_text = ""
                buffer = ""

                async for chunk in self.model_manager.process_content(
                    model_name=model,
                    model_version=version,
                    content=message.caption or "Analyze this video",
                    content_type="video",
                    file_path=video_path,
                    chat_history=formatted_history,
                    **params
                ):
                    response_text += chunk
                    buffer += chunk

                    if len(buffer) >= 100:
                        await self.message_handler.edit_message_safely(
                            status_message,
                            response_text,
                            reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                                status_message.id
                            )
                        )
                        buffer = ""
                        await asyncio.sleep(0.1)

                # Final update
                if response_text:
                    await self.message_handler.edit_message_safely(
                        status_message,
                        response_text,
                        reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                            status_message.id
                        )
                    )

                # Save to database
                self.db.add_message(
                    chat_id=self.active_chats[user_id],
                    role="user",
                    content=message.caption or "",
                    content_type="video",
                    file_path=video_path,
                    telegram_message_id=message.id
                )

                self.db.add_message(
                    chat_id=self.active_chats[user_id],
                    role="assistant",
                    content=response_text,
                    telegram_message_id=status_message.id,
                    model_params=params
                )
                 # Get language code from database
                chat_info = self.db.get_chat_info(self.active_chats[user_id])
                lang_code = 'en-US'  # Default language
                if chat_info:
                    lang_code = chat_info.get('lang_code', 'en-US')

                 # Send voice message
                await self._send_voice_message(status_message, response_text, lang_code)
            except Exception as e:
                logger.error(f"Error processing video: {str(e)}")
                await status_message.edit_text(
                    f"❌ Error processing video. Please try again later.",
                    reply_markup=self.keyboard_manager.get_general_back_keyboard("back_to_options")
                )
    
    async def handle_audio_message(self, message: Message):
            """Handle audio and voice messages"""
            user_id = message.from_user.id

            # Validate user settings
            model, version, params = self.db.get_user_settings(user_id)
            if not model or not version:
                await message.reply_text("⚠️ Please select a model first using /start")
                return

            if "audio" not in MODELS[model]["supported_inputs"]:
                await message.reply_text(
                    f"⚠️ The selected model ({model}) doesn't support audio input."
                )
                return

            try:
                status_message = await message.reply_text(
                    "🎵 Processing audio...",
                    reply_to_message_id=message.id
                )

                # Handle both audio files and voice messages
                os.makedirs("temp", exist_ok=True)
                file_ext = ".ogg" if message.voice else ".mp3"
                audio_path = os.path.join(
                    "temp",
                    f"{user_id}_{message.id}_audio{file_ext}"
                )
                await message.download(file_name=audio_path)

                # Store file path for regeneration
                self.temp_files[str(message.id)] = {
                    "path": audio_path,
                    "type": "audio"
                }

                # Get chat history
                chat_history = self.db.get_chat_history(self.active_chats[user_id])
                formatted_history = []
                for msg in chat_history:
                    formatted_history.append({
                        "role": msg["role"],
                        "content": msg["content"],
                        "content_type": msg.get("content_type", "text")
                    })

                response_text = ""
                buffer = ""

                async for chunk in self.model_manager.process_content(
                    model_name=model,
                    model_version=version,
                    content=message.caption or "Analyze this audio",
                    content_type="audio",
                    file_path=audio_path,
                    chat_history=formatted_history,
                    **params
                ):
                    response_text += chunk
                    buffer += chunk

                    if len(buffer) >= 100:
                        await self.message_handler.edit_message_safely(
                            status_message,
                            response_text,
                            reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                                status_message.id
                            )
                        )
                        buffer = ""
                        await asyncio.sleep(0.1)

                # Final update
                if response_text:
                    await self.message_handler.edit_message_safely(
                        status_message,
                        response_text,
                        reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                            status_message.id
                        )
                    )

                # Save to database
                self.db.add_message(
                    chat_id=self.active_chats[user_id],
                    role="user",
                    content=message.caption or "",
                    content_type="audio",
                    file_path=audio_path,
                    telegram_message_id=message.id
                )

                self.db.add_message(
                    chat_id=self.active_chats[user_id],
                    role="assistant",
                    content=response_text,
                    telegram_message_id=status_message.id,
                    model_params=params
                )
                # Get language code from database
                chat_info = self.db.get_chat_info(self.active_chats[user_id])
                lang_code = 'en-US'  # Default language
                if chat_info:
                   lang_code = chat_info.get('lang_code', 'en-US')

                 # Send voice message
                await self._send_voice_message(status_message, response_text, lang_code)

            except Exception as e:
                logger.error(f"Error processing audio: {str(e)}")
                await status_message.edit_text(
                    f"❌ Error processing audio. Please try again later.",
                    reply_markup=self.keyboard_manager.get_general_back_keyboard("back_to_options")
                )

    async def handle_document_message(self, message: Message):
        """Handle document messages"""
        user_id = message.from_user.id

        # Validate user settings
        model, version, params = self.db.get_user_settings(user_id)
        if not model or not version:
            await message.reply_text("⚠️ Please select a model first using /start")
            return

        if user_id not in self.active_chats:
            await message.reply_text(
                "Please start a new chat first:",
                reply_markup=self.keyboard_manager.get_chat_options_keyboard()
            )
            return

        try:
            status_message = await message.reply_text(
                "📄 Processing document...",
                reply_to_message_id=message.id
            )

            # Download document
            os.makedirs("temp", exist_ok=True)
            doc_path = os.path.join(
                "temp",
                f"{user_id}_{message.id}_{message.document.file_name}"
            )
            await message.download(file_name=doc_path)

            # Store file path for regeneration
            self.temp_files[str(message.id)] = {
                "path": doc_path,
                "type": "document"
            }

            # Get chat history
            chat_history = self.db.get_chat_history(self.active_chats[user_id])
            formatted_history = []
            for msg in chat_history:
                formatted_history.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "content_type": msg.get("content_type", "text")
                })

            response_text = ""
            buffer = ""

            async for chunk in self.model_manager.process_content(
                model_name=model,
                model_version=version,
                content=message.caption or f"Analyze this document: {message.document.file_name}",
                content_type="document",
                file_path=doc_path,
                chat_history=formatted_history,
                **params
            ):
                response_text += chunk
                buffer += chunk

                # Update message periodically to avoid flood limits
                if len(buffer) >= 100:
                    await self.message_handler.edit_message_safely(
                        status_message,
                        response_text,
                        reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                            status_message.id
                        )
                    )
                    buffer = ""
                    await asyncio.sleep(0.1)

            # Final update
            if response_text:
                await self.message_handler.edit_message_safely(
                    status_message,
                    response_text,
                    reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                        status_message.id
                    )
                )

            # Save to database
            self.db.add_message(
                chat_id=self.active_chats[user_id],
                role="user",
                content=message.caption or "",
                content_type="document",
                file_path=doc_path,
                telegram_message_id=message.id
            )

            self.db.add_message(
                chat_id=self.active_chats[user_id],
                role="assistant",
                content=response_text,
                telegram_message_id=status_message.id,
                model_params=params
            )
            # Get language code from database
            chat_info = self.db.get_chat_info(self.active_chats[user_id])
            lang_code = 'en-US'  # Default language
            if chat_info:
                lang_code = chat_info.get('lang_code', 'en-US')

             # Send voice message
            await self._send_voice_message(status_message, response_text, lang_code)


        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            await status_message.edit_text(
                f"❌ Error processing document. Please try again later.",
                reply_markup=self.keyboard_manager.get_general_back_keyboard("back_to_options")
            )
    
            
    async def handle_regeneration(self, callback_query: CallbackQuery):
        """Handle message regeneration"""
        try:
            user_id = callback_query.from_user.id
            message_id = int(callback_query.data.split(":")[1])

            if user_id not in self.active_chats:
                await callback_query.answer(
                    "No active chat found. Please start a new chat.",
                    show_alert=True
                )
                return

            chat_id = self.active_chats[user_id]
            all_messages = self.db.get_chat_history(chat_id)

            # Find the current message and its user message
            current_message = None
            user_message = None
            message_index = -1

            for i, msg in enumerate(all_messages):
                if msg["telegram_message_id"] == message_id:
                    current_message = msg
                    message_index = i
                    break

            if not current_message:
                await callback_query.answer(
                    "Message not found.",
                    show_alert=True
                )
                return

            # Find the corresponding user message
            for msg in reversed(all_messages[:message_index]):
                if msg["role"] == "user":
                    user_message = msg
                    break

            if not user_message:
                await callback_query.answer(
                    "Original message not found.",
                    show_alert=True
                )
                return

            # Validate user message content and type
            content = user_message.get("content", "").strip()
            content_type = user_message.get("content_type", "text")

            if not content and content_type == "text":
                await callback_query.answer(
                    "Cannot regenerate empty message.",
                    show_alert=True
                )
                return

            # Get user settings
            model, version, params = self.db.get_user_settings(user_id)

            # Get file path for non-text content
            file_path = None
            if content_type != "text":
                temp_file_info = self.temp_files.get(str(user_message["telegram_message_id"]))

                if temp_file_info and os.path.exists(temp_file_info["path"]):
                    file_path = temp_file_info["path"]
                elif user_message.get("file_path") and os.path.exists(user_message["file_path"]):
                    file_path = user_message["file_path"]

                if not file_path:
                    await callback_query.answer(
                        f"Original {content_type} file not found.",
                        show_alert=True
                    )
                    return

                # For media messages, if caption is empty, use default prompts
                if not content:
                    content = f"Analyze this {content_type}"

            # Delete any existing chunk messages
            await self.message_handler.delete_message_chunks(str(message_id))

            # Process with model
            await callback_query.message.edit_text(
                "🔄 Regenerating response..."
            )

            # Get chat history up to this point
            chat_history = []
            for msg in all_messages[:message_index]:
                if msg["telegram_message_id"] != message_id:  # Skip the message being regenerated
                    chat_history.append({
                        "role": msg["role"],
                        "content": msg["content"],
                        "content_type": msg.get("content_type", "text")
                    })

            response_text = ""
            buffer = ""

            async for chunk in self.model_manager.process_content(
                model_name=model,
                model_version=version,
                content=content,
                content_type=content_type,
                file_path=file_path,
                chat_history=chat_history,
                **params
            ):
                response_text += chunk
                buffer += chunk

                if len(buffer) >= 100:
                    await self.message_handler.edit_message_safely(
                        callback_query.message,
                        response_text,
                        reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                            callback_query.message.id
                        ),
                        content_type=content_type  # Pass the content type
                    )
                    buffer = ""
                    await asyncio.sleep(0.1)

            # Final update
            if response_text:
                await self.message_handler.edit_message_safely(
                    callback_query.message,
                    response_text,
                    reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                        callback_query.message.id
                    ),
                    content_type=content_type  # Pass the content type
                )

                # Add new message to database
                self.db.add_message(
                    chat_id=chat_id,
                    role="assistant",
                    content=response_text,
                    telegram_message_id=callback_query.message.id,
                    model_params=params,
                    content_type=content_type  # Save content type
                )
                # Get language code from database
                chat_info = self.db.get_chat_info(chat_id)
                lang_code = 'en-US'  # Default language
                if chat_info:
                  lang_code = chat_info.get('lang_code', 'en-US')

                 # Send voice message, and delete previous voice messages if exist
                await self._send_voice_message(callback_query.message, response_text, lang_code, delete_previous=True)
            else:
                await callback_query.message.edit_text(
                    "❌ Failed to generate response. Please try again.",
                    reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                        callback_query.message.id
                    )
                )

        except Exception as e:
            logger.error(f"Error in regeneration: {str(e)}")
            await callback_query.message.edit_text(
                f"❌ Error: Could not regenerate response. Please try again.",
                reply_markup=self.keyboard_manager.get_message_actions_keyboard(
                    callback_query.message.id
                )
            )
    
    async def handle_settings_callback(self, callback_query: CallbackQuery):
        """Handle settings-related callbacks"""
        try:
            data = callback_query.data
            user_id = callback_query.from_user.id
            message = callback_query.message
            
            logger.info(f"Processing settings callback - Data: {data} | User: {user_id}")
            
            # Get current settings
            model, version, current_params = self.db.get_user_settings(user_id)
            logger.info(f"Current settings - Model: {model} | Version: {version}")
            logger.info(f"Current parameters: {current_params}")

            if not current_params:
                logger.info("No current parameters found, using defaults")
                current_params = DEFAULT_PARAMS.copy()
                
            if data == "settings:advanced":
                logger.info("Showing advanced settings menu")
                settings_text = (
                    "🛠️ <b>Advanced Settings</b>\n\n"
                    f"Current settings for {model.upper()}:\n\n"
                )
                
                for param, value in current_params.items():
                    if param in PARAMETER_CONFIG:
                        precision = PARAMETER_CONFIG[param]["precision"]
                        formatted_value = round(float(value), precision) if precision > 0 else int(float(value))
                        settings_text += f"• <b>{param.replace('_', ' ').title()}:</b> {formatted_value}\n"
                
                settings_text += "\nClick on any parameter to adjust it."
                
                await message.edit_text(
                    settings_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=self.keyboard_manager.get_settings_keyboard(
                        model=model,
                        current_params=current_params
                    )
                )
                logger.info("Advanced settings menu displayed successfully")

            elif data.startswith(("inc_", "dec_")):
                action = data[:3]  # Get 'inc' or 'dec'
                param = data[4:]   # Get everything after inc_ or dec_
                
                logger.info(f"Parameter modification request - Action: {action} | Parameter: {param}")
                
                if param not in PARAMETER_CONFIG:
                    logger.error(f"Invalid parameter requested: {param}")
                    await callback_query.answer(
                        f"Invalid parameter: {param}",
                        show_alert=True
                    )
                    return

                # Get current value and limits
                current_value = float(current_params.get(param, PARAMETER_CONFIG[param]["min"]))
                step = float(PARAMETER_CONFIG[param]["step"])
                min_val = float(PARAMETER_CONFIG[param]["min"])
                max_val = float(PARAMETER_CONFIG[param]["max"])
                
                logger.info(f"Current value: {current_value} | Step: {step} | Min: {min_val} | Max: {max_val}")
                
                # Get parameter from callback data
                param = None
                if "_" in data:
                    parts = data.split("_")
                    if len(parts) > 2:  # For cases like adjust_top_p
                        param = "_".join(parts[1:])
                    else:  # For cases like inc_temperature
                        param = parts[1]
                    
                logger.info(f"Extracted parameter: {param}")

                # Calculate new value
                if action == "inc":
                    new_value = min(current_value + step, max_val)
                else:  # dec
                    new_value = max(current_value - step, min_val)
                
                logger.info(f"New calculated value: {new_value}")
                
                # Format value according to precision
                precision = PARAMETER_CONFIG[param]["precision"]
                new_value = round(new_value, precision) if precision > 0 else int(new_value)
                
                # Update parameters in database
                current_params[param] = new_value
                self.db.update_user_params(user_id, current_params)
                logger.info(f"Database updated with new value: {new_value} for {param}")
                
                # Update model parameters
                success = await self.model_manager.update_model_params(
                    model_name=model,
                    model_version=version,
                    params=current_params
                )
                logger.info(f"Model parameters update {'successful' if success else 'failed'}")
                
                # Update display
                param_display = param.replace("_", " ").title()
                await message.edit_text(
                    f"<b>Adjusting {param_display}</b>\n\n"
                    f"Current Value: {new_value}\n\n"
                    f"Description: {PARAMETER_CONFIG[param]['description']}\n\n"
                    f"{PARAMETER_CONFIG[param]['detail']}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=self.keyboard_manager.get_parameter_adjustment_keyboard(
                        param,
                        new_value,
                        PARAMETER_CONFIG[param]
                    )
                )
                
                # Show success message
                await callback_query.answer(
                    f"{param_display} updated to {new_value}" + (" ✅" if success else " ⚠️"),
                    show_alert=False
                )

            elif data.startswith("adjust_"):
                param = data[7:]  # Get everything after adjust_
                logger.info(f"Opening adjustment menu for parameter: {param}")
                
                if param not in PARAMETER_CONFIG:
                    logger.error(f"Invalid parameter for adjustment: {param}")
                    await callback_query.answer(
                        f"Invalid parameter: {param}",
                        show_alert=True
                    )
                    return
                
                current_value = current_params.get(param, PARAMETER_CONFIG[param]["min"])
                config = PARAMETER_CONFIG[param]
                
                logger.info(f"Current value: {current_value} | Config: {config}")
                
                await message.edit_text(
                    f"<b>Adjusting {param.replace('_', ' ').title()}</b>\n\n"
                    f"Current Value: {current_value}\n\n"
                    f"Description: {config['description']}\n\n"
                    f"{config['detail']}",
                    parse_mode=ParseMode.HTML,
                    reply_markup=self.keyboard_manager.get_parameter_adjustment_keyboard(
                        param,
                        current_value,
                        config
                    )
                )
                logger.info("Adjustment menu displayed successfully")

            elif data == "settings_help":
                logger.info("Opening settings help menu")
                help_text = (
                    "📚 <b>Settings Guide</b>\n\n"
                    "<b>Temperature (Creativity)</b>\n"
                    "Controls how creative or focused the responses are.\n"
                    "• Lower = more focused and precise\n"
                    "• Higher = more creative and varied\n\n"
                    "<b>Top P (Diversity)</b>\n"
                    "Controls how varied the word choices are.\n"
                    "• Lower = more conservative choices\n"
                    "• Higher = more diverse vocabulary\n\n"
                    "<b>Top K (Range)</b>\n"
                    "Limits the vocabulary range.\n"
                    "• Lower = strict vocabulary\n"
                    "• Higher = broader word selection\n\n"
                    "<b>Max Tokens (Length)</b>\n"
                    "Sets maximum response length.\n"
                    "• Lower = shorter responses\n"
                    "• Higher = longer, detailed responses\n\n"
                    "Note: For most conversations, the default values work well."
                )
                
                await message.edit_text(
                    help_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=self.keyboard_manager.get_settings_help_keyboard()
                )
                logger.info("Help menu displayed successfully")

            elif data == "back_to_settings":
                logger.info("Returning to main settings menu")
                settings_text = (
                    "🛠️ <b>Advanced Settings</b>\n\n"
                    f"Current settings for {model.upper()}:\n\n"
                )
                
                for param, value in current_params.items():
                    if param in PARAMETER_CONFIG:
                        precision = PARAMETER_CONFIG[param]["precision"]
                        formatted_value = round(float(value), precision) if precision > 0 else int(float(value))
                        settings_text += f"• <b>{param.replace('_', ' ').title()}:</b> {formatted_value}\n"
                
                await message.edit_text(
                    settings_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=self.keyboard_manager.get_settings_keyboard(
                        model=model,
                        current_params=current_params
                    )
                )
                logger.info("Returned to settings menu successfully")

            elif data == "back_to_message":
                logger.info("Returning to original message")
                # Restore original message state
                stored_content = self.message_contents.get(str(message.id))
                if stored_content:
                    if stored_content.get('chunks', []):
                        logger.info("Restoring multi-part message")
                        await self.message_handler.restore_messages(str(message.id), message)
                    else:
                        logger.info("Restoring single message")
                        await message.edit_text(
                            stored_content['text'],
                            reply_markup=self.keyboard_manager.get_message_actions_keyboard(message.id)
                        )
                    del self.message_contents[str(message.id)]
                else:
                    logger.info("No stored content found, using default message")
                    await message.edit_text(
                        "Send a message to continue!",
                        reply_markup=self.keyboard_manager.get_message_actions_keyboard(message.id)
                    )

            else:
                logger.warning(f"Unknown callback data received: {data}")
                await callback_query.answer(
                    "Unknown action",
                    show_alert=True
                )

        except Exception as e:
            logger.error(f"Error in settings callback: {str(e)}", exc_info=True)
            await callback_query.answer(
                "❌ An error occurred. Please try again.",
                show_alert=True
            )
    

    async def handle_model_settings(self, callback_query: CallbackQuery):
        """Handle model settings button"""
        user_id = callback_query.from_user.id
        model, version, params = self.db.get_user_settings(user_id)
        
        if not model:
            await callback_query.answer("Please select a model first", show_alert=True)
            return
        
        # Create a new callback query with settings:advanced data
        new_callback = CallbackQuery(
            id=callback_query.id,
            from_user=callback_query.from_user,
            chat_instance=callback_query.chat_instance,
            message=callback_query.message,
            data="settings:advanced"
        )
        
        await self.handle_settings_callback(new_callback)

    async def handle_change_model(self, callback_query: CallbackQuery):
        """Handle model change request"""
        await callback_query.message.edit_text(
            "Select a new model:",
            reply_markup=self.keyboard_manager.get_model_selection_keyboard()
        )

    async def handle_cancel(self, message: Message):
        """Handle /cancel command"""
        user_id = message.from_user.id
        
        if user_id in self.user_states:
            del self.user_states[user_id]
        
        if user_id in self.temp_data:
            del self.temp_data[user_id]
        
        if user_id in self.rename_states:
            del self.rename_states[user_id]
        
        await message.reply_text(
            "❌ Current operation cancelled. You can:\n"
            "• Use /start to select a different model\n"
            "• Start a new chat\n"
            "• Continue with your current chat",
            reply_markup=self.keyboard_manager.get_chat_options_keyboard()
        )

    async def _get_original_message(self, message_id: int) -> Optional[Dict]:
        """Get original message content from database"""
        message = self.db.get_message_by_telegram_id(message_id)
        if message:
            return {"content": message["content"]}
        return None


    async def handle_export_chat(self, callback_query: CallbackQuery):
        """Handle chat export request"""
        try:
            chat_id = int(callback_query.data.split(":")[1])
            
            await callback_query.message.edit_text(
                "📤 Select export format:",
                reply_markup=self.keyboard_manager.get_export_format_keyboard(chat_id)
            )
            
        except Exception as e:
            logger.error(f"Error handling export chat: {str(e)}")
            await callback_query.answer(
                "❌ Error initiating export.",
                show_alert=True
            )

    async def handle_export_format(self, callback_query: CallbackQuery):
        """Handle export format selection"""
        try:
            _, chat_id, format_type = callback_query.data.split(":")
            chat_id = int(chat_id)
            
            # Show processing message
            await callback_query.message.edit_text(
                f"📊 Processing export to {format_type.upper()}...\n"
                "Please wait..."
            )
            
            # Get chat history
            messages = self.db.get_chat_history(chat_id)
            if not messages:
                await callback_query.answer(
                    "No messages to export.",
                    show_alert=True
                )
                return
            
            # Get chat title
            chat_info = self.db.get_chat_info(chat_id)
            chat_title = chat_info["title"].replace(" ", "_")
            
            # Export chat
            exported_file = await self.export_manager.export_chat(
                chat_id=chat_id,
                messages=messages,
                format_type=format_type,
                chat_title=chat_title
            )
            
            # Send file
            with open(exported_file, 'rb') as f:
                await callback_query.message.reply_document(
                    document=f,
                    caption=f"📥 Chat export - {chat_title}\n"
                            f"Format: {format_type.upper()}\n"
                            f"Messages: {len(messages)}"
                )
            
            # Clean up
            try:
                os.remove(exported_file)
            except Exception as e:
                logger.error(f"Error removing exported file: {str(e)}")
            
            # Return to chat management menu
            await callback_query.message.edit_text(
                "What would you like to do with this chat?",
                reply_markup=self.keyboard_manager.get_chat_management_keyboard(chat_id)
            )
            
        except Exception as e:
            logger.error(f"Error exporting chat: {str(e)}")
            await callback_query.message.edit_text(
                "❌ Error exporting chat. Please try again.",
                reply_markup=self.keyboard_manager.get_chat_management_keyboard(int(chat_id))
            )

    def get_chat_info(self, chat_id: int) -> Optional[Dict]:
        """Get chat information"""
        cursor = self.conn.cursor()
        cursor.execute(
            '''SELECT chat_id, user_id, title, model, model_version, created_at
            FROM chats 
            WHERE chat_id = ? AND is_deleted = 0''',
            (chat_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "chat_id": row[0],
                "user_id": row[1],
                "title": row[2],
                "model": row[3],
                "model_version": row[4],
                "created_at": row[5]
            }
        return None
    

    def cleanup_old_files(self):
        """Clean up old temporary files"""
        try:
            current_time = time.time()
            files_to_remove = []
            
            # Check temp directory for old files
            for filename in os.listdir("temp"):
                file_path = os.path.join("temp", filename)
                # Remove files older than 1 hour
                if os.path.isfile(file_path) and current_time - os.path.getctime(file_path) > 3600:
                    try:
                        os.remove(file_path)
                        # Remove from temp_files if it exists
                        for msg_id, file_info in list(self.temp_files.items()):
                            if file_info.get("path") == file_path:
                                del self.temp_files[msg_id]
                    except OSError as e:
                        logger.error(f"Error removing old file {file_path}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in cleanup_old_files: {str(e)}")

    async def periodic_cleanup(self):
        """Run cleanup periodically"""
        while True:
            self.cleanup_old_files()
            await asyncio.sleep(1800)  # Run every 30 minutes


    def run(self):
        """Run the bot"""
        logger.info("🚀 Starting AI Bot...")
        try:
            # Start cleanup task
            self.app.loop.create_task(self.periodic_cleanup())
            
            # Run the bot
            self.app.run()
        except Exception as e:
            logger.error(f"❌ Error running bot: {str(e)}")
            raise