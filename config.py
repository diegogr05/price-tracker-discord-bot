import os
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "1440"))
DATABASE_PATH = os.getenv("DATABASE_PATH", "data.db")
USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; PriceBot/1.0)")
NOTIFY_CHANNEL_ID = os.getenv("NOTIFY_CHANNEL_ID")
