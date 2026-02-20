import os
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
INDEX_NAME = "mental-health-chatbot"

def reset_index():
    print(f"--- WARNING: This will DELETE ALL VECTORS in index '{INDEX_NAME}' ---")
    confirm = input("Are you sure? (Type 'yes' to confirm): ")
    
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        return

    print("Connecting to Pinecone...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(INDEX_NAME)
    
    print("Deleting all vectors...")
    try:
        index.delete(delete_all=True)
        print("✓ Successfully deleted all vectors.")
        
        # Also remove the local state file so store_index.py knows to re-index everything
        if os.path.exists("indexing_state.json"):
            os.remove("indexing_state.json")
            print("✓ Removed local indexing_state.json")
            
        print("\nIndex is now empty. Please run 'python store_index.py' to re-index specifically the files you want.")
        
    except Exception as e:
        print(f"Error deleting vectors: {e}")

if __name__ == "__main__":
    reset_index()
