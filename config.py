# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# AI Model API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

# Gemini TTS Cookies
GEMINI_TTS_SID = os.getenv("GEMINI_TTS_SID")
GEMINI_TTS_PSID = os.getenv("GEMINI_TTS_PSID")
GEMINI_TTS_HSID = os.getenv("GEMINI_TTS_HSID")
GEMINI_TTS_SSID = os.getenv("GEMINI_TTS_SSID")
GEMINI_TTS_APISID = os.getenv("GEMINI_TTS_APISID")
GEMINI_TTS_SAPISID = os.getenv("GEMINI_TTS_SAPISID")
GEMINI_TTS_1PSIDTS = os.getenv("GEMINI_TTS_1PSIDTS")
GEMINI_TTS_3PSIDTS = os.getenv("GEMINI_TTS_3PSIDTS")

# Gemini TTS AT Token
GEMINI_TTS_AT_TOKEN = os.getenv("GEMINI_TTS_AT_TOKEN")
    


# Model Configurations
MODELS = {
    "gemini": {
        "versions": [
            "gemini-1.5-flash-002",
            "gemini-1.5-pro-002",
            "gemini-2.0-flash-exp"
        ],
        "supported_inputs": ["text", "image", "video", "audio", "document"],
        "max_request_size": 20 * 1024 * 1024,  # 20MB per request
        "max_project_storage": 20 * 1024 * 1024 * 1024,  # 20GB per project
        "max_tokens_per_request": 20000,  # Maximum tokens per request
        "supported_formats": {
            "image": [
                ".jpg", ".jpeg", ".png", ".webp", 
                ".heic", ".heif", ".gif"
            ],
            "video": [
                ".mp4", ".webm", ".mov", 
                ".avi", ".mkv"  # Common video formats
            ],
            "audio": [
                ".mp3", ".wav", ".m4a", ".ogg",
                ".aac", ".flac"  # Common audio formats
            ],
            "document": [
                # Text and Documents
                ".txt", ".pdf", ".doc", ".docx", 
                ".rtf", ".odt", ".md", ".rst",
                # Code Files
                ".py", ".js", ".java", ".cpp", ".c",
                ".cs", ".go", ".rs", ".swift", ".kt",
                ".php", ".rb", ".pl", ".sh",
                # Web Files
                ".html", ".css", ".scss", ".less",
                ".jsx", ".tsx", ".vue", ".svelte",
                # Data Formats
                ".json", ".yaml", ".yml", ".xml",
                ".csv", ".tsv", ".sql",
                # Config Files
                ".ini", ".conf", ".env", ".cfg",
                # Documentation
                ".ipynb", ".tex"
            ]
        },
        "limits": {
            "image": {
                "max_size": 20 * 1024 * 1024,  # 20MB
                "max_resolution": 3072,  # 3072x3072 pixels maximum
                "supported_mime_types": [
                    "image/jpeg", "image/png", "image/webp",
                    "image/heic", "image/heif", "image/gif"
                ]
            },
            "video": {
                "max_size": 20 * 1024 * 1024,  # 20MB
                "max_duration": 60 * 2,  # 2 minutes
                "max_resolution": 1920,  # 1080p
                "supported_mime_types": [
                    "video/mp4", "video/webm", "video/quicktime",
                    "video/x-msvideo", "video/x-matroska"
                ]
            },
            "audio": {
                "max_size": 20 * 1024 * 1024,  # 20MB
                "max_duration": 60 * 2,  # 2 minutes
                "supported_mime_types": [
                    "audio/mpeg", "audio/wav", "audio/m4a",
                    "audio/ogg", "audio/aac", "audio/flac"
                ]
            },
            "document": {
                "max_size": 20 * 1024 * 1024,  # 20MB
                "max_pages": 2000,  # For PDFs
                "max_characters": 100000  # For text documents
            }
        }
    },
    "claude": {
        "versions": [
            "claude-3.5-haiku",
            "claude-3.5-sonnet"
        ],
        "supported_inputs": ["text", "image"],
        "max_request_size": 100 * 1024 * 1024  # 100MB
    },
    "deepseek": {
        "versions": ["deepseek-v3"],
        "supported_inputs": ["text"],
        "max_request_size": 4 * 1024 * 1024  # 4MB
    }
}

# Default Parameters
DEFAULT_PARAMS = {
    "temperature": 0.7,
    "top_p": 0.95,
    "top_k": 40,
    "max_tokens": 2048
}

# Parameter Configurations
# Parameter Configurations
PARAMETER_CONFIG = {
    "temperature": {
        "min": 0.0,
        "max": 2.0,
        "step": 0.1,
        "precision": 1,
        "description": "Controls response randomness",
        "detail": (
            "🌡️ Temperature affects how creative or focused the response is:\n\n"
            "• Low (0.1-0.3): More focused, consistent responses\n"
            "• Medium (0.4-0.7): Balanced creativity and focus\n"
            "• High (0.8+): More creative, varied responses\n\n"
            "Recommended:\n"
            "• Code/Technical: 0.2-0.3\n"
            "• General Chat: 0.6-0.7\n"
            "• Creative Tasks: 0.8-1.0"
        )
    },
    "top_p": {
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "precision": 2,
        "description": "Controls response diversity",
        "detail": (
            "🎯 Top_p (nucleus sampling) affects word choice variety:\n\n"
            "• Low (0.1-0.3): Uses only most likely words\n"
            "• Medium (0.4-0.7): Balanced variety\n"
            "• High (0.8+): More diverse vocabulary\n\n"
            "Recommended:\n"
            "• Technical: 0.1-0.3\n"
            "• General: 0.7\n"
            "• Creative: 0.9-1.0"
        )
    },
    "top_k": {
        "min": 1,
        "max": 100,
        "step": 1,
        "precision": 0,
        "description": "Controls vocabulary range",
        "detail": (
            "🔝 Top_k limits the number of words to choose from:\n\n"
            "• Low (1-20): Very focused vocabulary\n"
            "• Medium (20-50): Normal range\n"
            "• High (50+): Broader word selection\n\n"
            "Recommended:\n"
            "• Technical: 10-20\n"
            "• General: 40\n"
            "• Creative: 50+"
        )
    },
    "max_tokens": {
        "min": 64,
        "max": 8192,
        "step": 64,
        "precision": 0,
        "description": "Maximum response length",
        "detail": (
            "📝 Max_tokens sets the maximum response length:\n\n"
            "• Short (64-512): Quick responses\n"
            "• Medium (512-2048): Normal conversations\n"
            "• Long (2048+): Detailed explanations\n\n"
            "Recommended:\n"
            "• Quick answers: 256\n"
            "• Normal chat: 1024\n"
            "• Detailed: 2048+"
        )
    }
}

# Supported languages for Gemini TTS
SUPPORTED_LANGUAGES = {
    'en-US': {'name': 'English', 'sample_text': 'Hello, this is a test message.'},
    'fr-FR': {'name': 'French', 'sample_text': 'Bonjour, ceci est un message test.'},
    'de-DE': {'name': 'German', 'sample_text': 'Hallo, dies ist eine Testnachricht.'},
    'es-ES': {'name': 'Spanish', 'sample_text': 'Hola, este es un mensaje de prueba.'},
    'it-IT': {'name': 'Italian', 'sample_text': 'Ciao, questo è un messaggio di prova.'},
    'pt-PT': {'name': 'Portuguese', 'sample_text': 'Olá, esta é uma mensagem de teste.'},
    'ru-RU': {'name': 'Russian', 'sample_text': 'Привет, это тестовое сообщение.'},
    'ja-JP': {'name': 'Japanese', 'sample_text': 'こんにちは、これはテストメッセージです。'},
    'ko-KR': {'name': 'Korean', 'sample_text': '안녕하세요, 이것은 테스트 메시지입니다.'},
    'zh-CN': {'name': 'Chinese (Simplified)', 'sample_text': '你好，这是一条测试消息。'},
    'ar-AE': {'name': 'Arabic', 'sample_text': 'مرحبا، هذه رسالة اختبار.'},
    'hi-IN': {'name': 'Hindi', 'sample_text': 'नमस्ते, यह एक परीक्षण संदेश है।'},
    'fa-IR': {'name': 'Persian', 'sample_text': 'سلام، این یک پیام آزمایشی است.'}
}
    
