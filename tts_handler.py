import requests
import json
import base64
import urllib.parse
import time
from pathlib import Path
import logging

from config import (
        GEMINI_TTS_SID,
        GEMINI_TTS_PSID,
        GEMINI_TTS_HSID,
        GEMINI_TTS_SSID,
        GEMINI_TTS_APISID,
        GEMINI_TTS_SAPISID,
        GEMINI_TTS_1PSIDTS,
        GEMINI_TTS_3PSIDTS,
        GEMINI_TTS_AT_TOKEN,
        SUPPORTED_LANGUAGES
    )

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("gemini_tts_debug.log"),
        logging.StreamHandler()
    ]
)

class GeminiTTS:
    def __init__(self):
        self.base_url = "https://gemini.google.com/_/BardChatUi/data/batchexecute"
        self.supported_languages = SUPPORTED_LANGUAGES
        
        # Create output directory for audio files
        self.output_dir = Path("gemini_tts_outputs")
        self.output_dir.mkdir(exist_ok=True)
        
        # Cookies (replace with valid ones)
        self.cookies = {
                'SID': GEMINI_TTS_SID,
                '__Secure-1PSID': GEMINI_TTS_PSID,
                'HSID': GEMINI_TTS_HSID,
                'SSID': GEMINI_TTS_SSID,
                'APISID': GEMINI_TTS_APISID,
                'SAPISID': GEMINI_TTS_SAPISID,
                '__Secure-1PSIDTS': GEMINI_TTS_1PSIDTS,
                '__Secure-3PSIDTS': GEMINI_TTS_3PSIDTS,
            }
        
        
        # Headers for the request
        self.headers = {
            'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
            'origin': 'https://gemini.google.com',
            'referer': 'https://gemini.google.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'x-same-domain': '1'
        }
        
        # Token for the request
        self.at_token = GEMINI_TTS_AT_TOKEN

        # Supported languages
        self.supported_languages = {
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

    def _prepare_request_data(self, text, lang):
        """Prepare the request payload."""
        f_req_data = [[[
            "XqA3Ic",
            json.dumps([None, text, lang, None, 2]),
            None,
            "generic"
        ]]]
        encoded_data = urllib.parse.quote(json.dumps(f_req_data))
        return f"f.req={encoded_data}&at={self.at_token}&"

    def _extract_audio_data(self, response_text):
        """Extract audio data from the response."""
        try:
            json_str = response_text.replace(")]}'", "").strip()
            lines = json_str.split('\n')
            if len(lines) < 2:
                logging.error("Response has fewer lines than expected.")
                return None
            
            try:
                data = json.loads(lines[1])
                if isinstance(data, list) and len(data) > 0:
                    audio_data = data[0][2]
                    if audio_data:
                        return base64.b64decode(audio_data)
            except json.JSONDecodeError as e:
                logging.error(f"JSON decode error: {e}")
                logging.error(f"Response text: {response_text}")
            
            return None
        except Exception as e:
            logging.error(f"Error extracting audio data: {e}")
            return None

    def text_to_speech(self, text, lang_code):
        """Convert text to speech and save the audio file."""
        params = {
            'rpcids': 'XqA3Ic',
            'source-path': '/app/6eb3adea0a705e85',
            'bl': 'boq_assistant-bard-web-server_20250106.05_p1',
            'f.sid': '-7464670970805767250',
            'hl': lang_code,  # Use full language code
            '_reqid': '3837149',
            'rt': 'c'
        }

        data = self._prepare_request_data(text, lang_code)
        
        try:
            logging.info(f"Sending request for language: {lang_code}")
            logging.debug(f"Request params: {params}")
            logging.debug(f"Request data: {data}")
            
            response = requests.post(
                self.base_url,
                params=params,
                headers=self.headers,
                cookies=self.cookies,
                data=data,
                timeout=30
            )
            
            logging.info(f"Response status code: {response.status_code}")
            logging.debug(f"Response headers: {response.headers}")
            logging.debug(f"Response text: {response.text}")
            
            if response.status_code == 200:
                logging.info(f"Response size: {len(response.content)} bytes")
                
                audio_data = self._extract_audio_data(response.text)
                if audio_data:
                    filename = self.output_dir / f'tts_{lang_code}_{int(time.time())}.mp3'
                    with open(filename, 'wb') as f:
                        f.write(audio_data)
                    logging.info(f"Success! Audio saved to: {filename}")
                    return True
                else:
                    error_file = self.output_dir / f'error_{lang_code}_{int(time.time())}.txt'
                    with open(error_file, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    logging.error(f"Could not extract audio. Response saved to: {error_file}")
                    return False
            else:
                logging.error(f"Error {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logging.error(f"Error occurred: {e}")
            return False