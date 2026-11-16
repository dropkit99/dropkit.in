import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler

# Setup path so backend package can be imported
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Ensure database is seeded/initialized on cold start
try:
    from backend.db import init_db
    init_db()
except Exception as e:
    print(f"Warning initializing DB: {e}")

from backend.server import DropKitHandler

# Vercel Serverless Function entrypoint
class handler(DropKitHandler):
    pass
