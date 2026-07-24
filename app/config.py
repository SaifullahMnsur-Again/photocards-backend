import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_DIR = os.path.join(BASE_DIR, "app", "media")
WEIGHTS_DIR = os.path.join(BASE_DIR, "app", "weights")

SERVER_DOMAIN = os.getenv("SERVER_DOMAIN", "https://photocards.saifullahmnsur.dev")

os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(WEIGHTS_DIR, exist_ok=True)