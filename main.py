# main.py
import logging
from bot_handler import AIBot
import os
import sqlite3


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_database(db_path: str):
    """Initialize database if it doesn't exist"""
    try:
        if not os.path.exists(db_path):
            logger.info(f"Creating new database file: {db_path}")
            # Create the database file
            conn = sqlite3.connect(db_path)
            conn.close()
            return True
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False

def main():
    try:
        # Initialize database
        db_path = "ai_chat.db"
        if not init_database(db_path):
            logger.error("Failed to initialize database")
            return

        # Initialize and run the bot
        logger.info("Initializing AI Bot...")
        bot = AIBot()
        logger.info("Starting AI Bot...")
        bot.run()
        
    except Exception as e:
        logger.error(f"Error starting bot: {str(e)}")
        raise

if __name__ == "__main__":
    main()