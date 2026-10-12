from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL")
DATABASE_NAME = os.getenv("DATABASE_NAME", "mushroom_db")

client: AsyncIOMotorClient = None
db = None

async def connect_to_mongo():
    global client, db
    client = AsyncIOMotorClient(MONGODB_URL, maxPoolSize=50, minPoolSize=10)
    db = client[DATABASE_NAME]
    print(f"Connected to MongoDB Atlas: {DATABASE_NAME}")

async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("Closed MongoDB connection pool.")

def get_database():
    return db