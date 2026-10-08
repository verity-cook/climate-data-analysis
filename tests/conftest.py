import os

for key in [
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
]:
    os.environ.setdefault(key, "test")