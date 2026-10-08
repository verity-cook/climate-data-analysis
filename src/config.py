import os

from dotenv import load_dotenv

load_dotenv()

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.environ["MINIO_ROOT_USER"]
S3_SECRET_KEY = os.environ["MINIO_ROOT_PASSWORD"]
S3_REGION = os.getenv("S3_REGION", "us-east-1")

RAW_BUCKET = os.getenv("RAW_BUCKET", "climate-raw")

SOURCE_URL = (
    "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
)

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ["POSTGRES_PORT"])
POSTGRES_USER = os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]
POSTGRES_DB = os.environ["POSTGRES_DB"]