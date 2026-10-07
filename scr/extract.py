import logging
from datetime import date

import boto3
import requests

from src import config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=config.S3_ENDPOINT,
        aws_access_key_id=config.S3_ACCESS_KEY,
        aws_secret_access_key=config.S3_SECRET_KEY,
        region_name=config.S3_REGION,
    )

def extract() -> str:
    log.info("Downloading %s", config.SOURCE_URL)
    response = requests.get(config.SOURCE_URL, timeout=60)
    response.raise_for_status()

    key = f"raw/{date.today().isoformat()}/owid-co2-data.csv"
    s3_client().put_object(
        Bucket=config.RAW_BUCKET, Key=key, Body=response.content
    )
    log.info(
        "Stored %d bytes at s3://%s/%s",
        len(response.content),
        config.RAW_BUCKET,
        key,
    )
    return key

if __name__ == "__main__":
    extract()