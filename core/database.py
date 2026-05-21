from pymongo import MongoClient
from supabase import create_client, Client
from flask import current_app

db = None
supabase: Client = None

def init_db(app):
    global db, supabase
    # Initialize MongoDB
    mongo_uri = app.config['MONGO_URI']
    db_name = app.config['MONGO_DB_NAME']
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    # Initialize Supabase
    supabase_url = app.config['SUPABASE_URL']
    supabase_key = app.config['SUPABASE_KEY']
    if supabase_url and supabase_key:
        supabase = create_client(supabase_url, supabase_key)
    else:
        app.logger.warning("Supabase URL or Key not provided. Supabase will not be initialized.")

def get_users_collection():
    if db is None:
        raise Exception("Database not initialized")
    return db.users

def get_chat_history_collection():
    if db is None:
        raise Exception("Database not initialized")
    return db.chat_history

def get_clones_collection():
    if db is None:
        raise Exception("Database not initialized")
    return db.clones

def upload_file_to_supabase(file_path: str, bucket_name: str, destination_path: str):
    """
    Upload a file to Supabase Storage.
    """
    if not supabase:
        raise Exception("Supabase is not initialized.")
    
    with open(file_path, 'rb') as f:
        res = supabase.storage.from_(bucket_name).upload(destination_path, f)
    return res

def download_file_from_supabase(bucket_name: str, file_path: str, destination: str):
    """
    Download a file from Supabase Storage to a local path.
    """
    if not supabase:
        raise Exception("Supabase is not initialized.")
        
    with open(destination, 'wb+') as f:
        res = supabase.storage.from_(bucket_name).download(file_path)
        f.write(res)
    return destination
