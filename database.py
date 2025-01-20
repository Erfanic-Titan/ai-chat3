# database.py
import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional, Dict
import json
import logging
from sqlite3 import Error as SQLiteError


logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_name: str):
        """Initialize database connection"""
        try:
            self.conn = sqlite3.connect(db_name, check_same_thread=False)
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.create_tables()
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise

    def create_tables(self):
        """Create necessary database tables"""
        cursor = self.conn.cursor()
        
        try:
            # Create users table first
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                selected_model TEXT,
                model_version TEXT,
                model_params TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            self.conn.commit()  # Commit after creating users table
            
            # Create chats table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                model TEXT NOT NULL,
                model_version TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0,
                lang_code TEXT DEFAULT 'en-US',
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
            ''')
            self.conn.commit()  # Commit after creating chats table
            
            # Create messages table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                content_type TEXT DEFAULT 'text',
                file_path TEXT,
                telegram_message_id INTEGER,
                model_params TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
            )
            ''')
            self.conn.commit()  # Commit after creating messages table
            
            # Verify tables were created
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            logger.info(f"Created tables: {[table[0] for table in tables]}")
            
        except sqlite3.Error as e:
            logger.error(f"Error creating tables: {str(e)}")
            self.conn.rollback()
            raise
        finally:
            cursor.close()

    def get_or_create_user(self, user_id: int) -> None:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        if not cursor.fetchone():
            cursor.execute(
                'INSERT INTO users (user_id) VALUES (?)',
                (user_id,)
            )
            self.conn.commit()

    def update_user_model(self, user_id: int, model: str, version: str) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            'UPDATE users SET selected_model = ?, model_version = ? WHERE user_id = ?',
            (model, version, user_id)
        )
        self.conn.commit()

    def update_user_params(self, user_id: int, params: dict) -> None:
        param_config = {
            "temperature": {"precision": 1, "min": 0.0, "max": 2.0},
            "top_p": {"precision": 2, "min": 0.0, "max": 1.0},
            "top_k": {"precision": 0, "min": 1, "max": 100},
            "max_tokens": {"precision": 0, "min": 64, "max": 4096}
        }

        formatted_params = {}
        for key, value in params.items():
            if key in param_config:
                value = float(value)
                value = max(param_config[key]["min"], min(param_config[key]["max"], value))
                if param_config[key]["precision"] == 0:
                    formatted_params[key] = int(value)
                else:
                    formatted_params[key] = round(value, param_config[key]["precision"])
            else:
                formatted_params[key] = value

        cursor = self.conn.cursor()
        cursor.execute(
            'UPDATE users SET model_params = ? WHERE user_id = ?',
            (json.dumps(formatted_params), user_id)
        )
        self.conn.commit()

    def get_user_settings(self, user_id: int) -> Tuple[Optional[str], Optional[str], Optional[dict]]:
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT selected_model, model_version, model_params FROM users WHERE user_id = ?',
            (user_id,)
        )
        result = cursor.fetchone()
        
        if result:
            model, version, params_str = result
            default_params = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_tokens": 2048
            }
            
            if params_str:
                try:
                    params = json.loads(params_str)
                    # Merge with defaults and ensure proper formatting
                    return model, version, {**default_params, **params}
                except json.JSONDecodeError:
                    return model, version, default_params
            return model, version, default_params
        return None, None, None

    def create_chat(self, user_id: int, title: str, model: str, version: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT INTO chats (user_id, title, model, model_version, lang_code) VALUES (?, ?, ?, ?, ?)',
            (user_id, title, model, version, 'en-US')
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_user_chats(self, user_id: int) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            '''SELECT chat_id, title, model, model_version, created_at 
               FROM chats 
               WHERE user_id = ? AND is_deleted = 0 
               ORDER BY created_at DESC''',
            (user_id,)
        )
        chats = []
        for row in cursor.fetchall():
            chats.append({
                "chat_id": row[0],
                "title": row[1],
                "model": row[2],
                "model_version": row[3],
                "created_at": row[4]
            })
        return chats

    def update_chat_title(self, chat_id: int, new_title: str) -> bool:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                'UPDATE chats SET title = ? WHERE chat_id = ?',
                (new_title, chat_id)
            )
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False

    def delete_chat(self, chat_id: int) -> bool:
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                'UPDATE chats SET is_deleted = 1 WHERE chat_id = ?',
                (chat_id,)
            )
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False

    def add_message(self, chat_id: int, role: str, content: str, 
                   content_type: str = 'text', file_path: Optional[str] = None,
                   telegram_message_id: Optional[int] = None,
                   model_params: Optional[dict] = None) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            '''INSERT INTO messages 
               (chat_id, role, content, content_type, file_path, 
                telegram_message_id, model_params)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (chat_id, role, content, content_type, file_path,
             telegram_message_id, json.dumps(model_params) if model_params else None)
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def update_message(self, message_id: int, new_content: str, new_telegram_message_id: Optional[int] = None) -> bool:
        """Update a message in the database"""
        cursor = self.conn.cursor()
        try:
            if new_telegram_message_id:
                cursor.execute(
                    '''UPDATE messages 
                    SET content = ?, telegram_message_id = ? 
                    WHERE message_id = ?''',
                    (new_content, new_telegram_message_id, message_id)
                )
            else:
                cursor.execute(
                    'UPDATE messages SET content = ? WHERE message_id = ?',
                    (new_content, message_id)
                )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error updating message: {str(e)}")
            return False

    def get_chat_info(self, chat_id: int) -> Optional[Dict]:
        """Get chat information"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                '''SELECT chat_id, user_id, title, model, model_version, created_at, lang_code
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
                    "created_at": row[5],
                    "lang_code": row[6]
                }
            return None
            
        except sqlite3.Error as e:
            logger.error(f"Error getting chat info for chat_id {chat_id}: {str(e)}")
            return None

    def get_chat_history(self, chat_id: int, limit: Optional[int] = None) -> List[Dict]:
        """Get chat history with all message details"""
        try:
            cursor = self.conn.cursor()
            query = '''
                SELECT role, content, content_type, file_path, 
                    telegram_message_id, model_params, timestamp
                FROM messages 
                WHERE chat_id = ?
                ORDER BY timestamp ASC
            '''
            
            if limit:
                query += f' LIMIT {limit}'
                
            cursor.execute(query, (chat_id,))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    "role": row[0],
                    "content": row[1],
                    "content_type": row[2],
                    "file_path": row[3],
                    "telegram_message_id": row[4],
                    "model_params": json.loads(row[5]) if row[5] else None,
                    "timestamp": row[6]
                })
            return messages
            
        except sqlite3.Error as e:
            logger.error(f"Error getting chat history for chat_id {chat_id}: {str(e)}")
            return []

    def get_message_by_telegram_id(self, telegram_message_id: int) -> Optional[Dict]:
        cursor = self.conn.cursor()
        cursor.execute(
            '''SELECT message_id, chat_id, role, content, content_type, file_path, 
            telegram_message_id, model_params, timestamp 
            FROM messages WHERE telegram_message_id = ?''',
            (telegram_message_id,)
        )
        row = cursor.fetchone()
        if row:
            column_names = ["message_id", "chat_id", "role", "content", "content_type", 
                        "file_path", "telegram_message_id", "model_params", "timestamp"]
            message_dict = dict(zip(column_names, row))
            if message_dict["model_params"]:
                try:
                    message_dict["model_params"] = json.loads(message_dict["model_params"])
                except json.JSONDecodeError:
                    message_dict["model_params"] = None
            return message_dict
        return None
    
    def update_chat_lang_code(self, chat_id: int, lang_code: str) -> bool:
        """Update the language code of a chat"""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                'UPDATE chats SET lang_code = ? WHERE chat_id = ?',
                (lang_code, chat_id)
            )
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False
    

    
    def __del__(self):
        """Ensure connection is closed when object is destroyed"""
        try:
            self.conn.close()
        except:
            pass