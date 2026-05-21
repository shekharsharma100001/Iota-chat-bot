from pinecone import Pinecone, ServerlessSpec
from flask import current_app

pc = None
index = None

def init_pinecone(app):
    global pc, index
    api_key = app.config.get('PINECONE_API_KEY')
    if api_key:
        pc = Pinecone(api_key=api_key)
        index_name = "echo-mind"
        
        # Check if index exists, else create it.
        # If it exists but has a legacy dimension (like 768), delete and recreate it.
        target_dim = 3072
        existing_indexes = pc.list_indexes().names()
        
        if index_name in existing_indexes:
            desc = pc.describe_index(index_name)
            if desc.dimension != target_dim:
                print(f"Pinecone index {index_name} has legacy dimension {desc.dimension}. Deleting and recreating with {target_dim} dimensions...")
                pc.delete_index(index_name)
                # Wait for delete to propagate if needed (handled by recreate loop)
                existing_indexes = pc.list_indexes().names()
        
        if index_name not in pc.list_indexes().names():
            pc.create_index(
                name=index_name,
                dimension=target_dim,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
        index = pc.Index(index_name)
    else:
        app.logger.warning("PINECONE_API_KEY is not set. Pinecone will not be initialized.")

def get_namespace(user_id: str, clone_id: str = "default") -> str:
    """Format the explicit, user-isolated namespace"""
    return f"ns_user_{user_id}_clone_{clone_id}"

def upsert_vectors(user_id: str, clone_id: str, vectors: list[dict]):
    """
    Upsert vectors to a specific user's namespace.
    vectors should be a list of dicts: {'id': str, 'values': list[float], 'metadata': dict}
    """
    if not index:
        raise Exception("Pinecone index not initialized.")
        
    namespace = get_namespace(user_id, clone_id)
    index.upsert(vectors=vectors, namespace=namespace)

def search_vectors(user_id: str, clone_id: str, query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """
    Search for semantic matches within the user's isolated namespace.
    """
    if not index:
        raise Exception("Pinecone index not initialized.")
        
    namespace = get_namespace(user_id, clone_id)
    response = index.query(
        namespace=namespace,
        vector=query_embedding,
        top_k=top_k,
        include_metadata=True
    )
    
    matches = []
    for match in response['matches']:
        matches.append(match['metadata'])
    return matches

def purge_namespace(user_id: str, clone_id: str = "default"):
    """
    Execute a wholesale purge against a specific namespace.
    """
    if not index:
        raise Exception("Pinecone index not initialized.")
        
    namespace = get_namespace(user_id, clone_id)
    index.delete(delete_all=True, namespace=namespace)
