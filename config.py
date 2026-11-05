import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

def get_credentials():
    api_key = os.getenv("GROWW_API_KEY", "").strip()
    totp_secret = os.getenv("GROWW_TOTP_SECRET", "").strip()

    # Fallback to key.txt if .env is missing or empty
    key_file = BASE_DIR / "key.txt"
    if (not api_key or not totp_secret) and key_file.exists():
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Parse TOTP Token No
                token_match = re.search(r"TOTP\s*Token\s*No\s*[-:]\s*([^\r\n]+)", content, re.IGNORECASE)
                if token_match and not api_key:
                    api_key = token_match.group(1).strip()

                # Parse TOTP QR CODE
                secret_match = re.search(r"TOTP\s*QR\s*CODE\s*[-:]\s*([^\r\n]+)", content, re.IGNORECASE)
                if secret_match and not totp_secret:
                    totp_secret = secret_match.group(1).strip()
        except Exception as e:
            print(f"[Config] Error reading key.txt: {e}")

    return {
        "api_key": api_key,
        "totp_secret": totp_secret,
        "flask_secret": os.getenv("FLASK_SECRET_KEY", "groww-default-secret-key"),
        "flask_port": int(os.getenv("FLASK_PORT", 5000)),
        "flask_debug": os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    }

CONFIG = get_credentials()

