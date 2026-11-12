import os
import sys

os.environ["MARKET_EXTENDED_MODE"] = "redirect"
os.environ["COMMUNITY_BASE_URL"] = "https://community.theindianfamily.shop"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.chdir(BASE_DIR)

from a2wsgi import ASGIMiddleware
from app.main import app as fastapi_app

application = ASGIMiddleware(fastapi_app)
