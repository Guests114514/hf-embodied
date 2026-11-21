OFFICIAL = "https://huggingface.co"
MIRROR = "https://hf-mirror.com"

BASE_URL = OFFICIAL
HEADERS = {"User-Agent": "hf-embodied-survey/0.1 (course project)"}
RAW_DIR = "raw"
DB_PATH = "hf.db"

SNAPSHOT_LIMIT = 100
SLEEP = 0.4
MAX_ORGS = 5
MAX_MEMBERS_PER_ORG = 60
BULK_UPLOADER_MIN_MODELS = 500

KEYWORDS = ["VLA", "embodied", "manipulation", "locomotion",
            "world model", "imitation learning", "sim2real", "humanoid"]
MIN_ORG_EMBODIED = 3
MIN_ORG_RATIO = 0.5
MIN_ORG_EMBLIKES = 50
TOP_V = 10
HOP2 = 15
MAX_NODES = 200
PROJECT_POOL = 20