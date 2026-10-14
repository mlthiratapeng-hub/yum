# config.py
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
PREFIX = "!"
OWNER_ID = 1488103702488154173

MAX_DURATION  = 350
MAX_THREADS   = 400

# ── API ──
API_BASE     = "https://api888.duckdns.org/attack"
API_KEY      = "snp5173be36a7cb6e2a5d52c0db2feef37d"
API_METHOD   = "HTTPS-BYPASS"

# ── Forbidden ──
FORBIDDEN_TLDS = []
FORBIDDEN_IPS  = ["127.0.0.1", "localhost", "0.0.0.0"]

# ── Paths ──
DATA_DIR       = os.path.join(BASE_DIR, "data")
DB_PATH        = os.path.join(DATA_DIR, "bot.db")
ATTACK_LOG_DIR = os.path.join(DATA_DIR, "attack_logs")

# ── Emojis ──
EMOJI_HEADER  = "<a:1000030144:1559280351254151199>"
EMOJI_CONTACT = "<:1000035915:1559174417097953340>"
EMOJI_ALLOWED = "<:1000039016:1559632194668855366>"
EMOJI_BUTTON  = "<:1000039019:1559634993997942834>"

# ── Prices ──
PRICE_TEXT = "วันละ 40 / ถาวร 300 TH"