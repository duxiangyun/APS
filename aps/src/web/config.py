import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "db", "aps_or.db")
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 500
CSV_ENCODING = "utf-8-sig"
