
import time
import hmac
import hashlib
import base64
import random
import string
from dotenv import load_dotenv
import os

load_dotenv()

APP_ID = os.getenv("HPD_APP_ID")
API_KEY = os.getenv("HPD_API_KEY")

def generate_nonce(length: int = 16):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def md5_base64(content: str) -> str:
    if not content:
        return "1B2M2Y8AsgTpgAmY7PhCfg=="
    return base64.b64encode(hashlib.md5(content.encode()).digest()).decode()

def generate_auth_header(method: str, path: str, query: str = "", body: str = "") -> str:
    method = method.upper()
    path = path.lower()
    timestamp = str(int(time.time()))
    nonce = generate_nonce()
    body_md5 = md5_base64(body)
    
    message = f"{APP_ID}{method}{path}{query}{timestamp}{nonce}{body_md5}"
    
    digest = base64.b64encode(
        hmac.new(API_KEY.encode(), message.encode(), hashlib.sha256).digest()
    ).decode()

    return f"smx {APP_ID}:{digest}:{timestamp}:{nonce}"
