import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
MEDIA_DIR = os.path.join(BASE_DIR, "media")
IMAGE_DIR = os.path.join(MEDIA_DIR, "images")

os.makedirs(IMAGE_DIR, exist_ok=True)

# Read environment variables with fallback defaults
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
SERVER_DOMAIN = os.getenv("SERVER_DOMAIN", "https://photocards.saifullahmnsur.dev")
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "default_fallback_admin_key_2026")