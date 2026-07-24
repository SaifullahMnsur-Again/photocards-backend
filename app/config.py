import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
MEDIA_DIR = os.path.join(BASE_DIR, "media")
IMAGE_DIR = os.path.join(MEDIA_DIR, "images")

os.makedirs(IMAGE_DIR, exist_ok=True)

# Central Configuration Variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
SERVER_DOMAIN = os.getenv("SERVER_DOMAIN", "https://photocards.saifullahmnsur.dev")
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "photocards_super_secret_key_2026")

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_DIR = os.path.join(BASE_DIR, "app", "media")
WEIGHTS_DIR = os.path.join(BASE_DIR, "app", "weights")

SERVER_DOMAIN = os.getenv("SERVER_DOMAIN", "https://photocards.saifullahmnsur.dev")

os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(WEIGHTS_DIR, exist_ok=True)