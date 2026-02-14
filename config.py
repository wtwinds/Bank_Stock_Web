# config.py
import os
from pymongo import MongoClient

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://lalitmahajan484_db_user:EjYIfU3Zi7SvzCNK@cluster0.0atbyqx.mongodb.net/Bank_db"
)

mongo_client = MongoClient(MONGO_URI)
bank_db = mongo_client.Bank_db
