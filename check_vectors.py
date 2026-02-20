import os
from dotenv import load_dotenv
from pinecone import Pinecone

# --- Configuration ---
DOCUMENT_NAME = r"C:\mental-health-chatbot\mental-health-chatbot-main\data\Burnout The Secret to Unlocking the Stress Cycle.pdf"  
# The name of the document you want to check
INDEX_NAME = "mental-health-chatbot"
# ---------------------

def check_document_vectors(doc_name):
    """Connects to Pinecone and checks for vectors from a specific document."""
    # Normalize the path for consistent matching
    doc_name = doc_name.replace("\\", "/")
    print(f"--- Checking for vectors from normalized path: {doc_name} ---")
    
    load_dotenv()
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

    if not PINECONE_API_KEY:
        print("ERROR: PINECONE_API_KEY not found in .env file!")
        return

    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(INDEX_NAME)
        print(f"Successfully connected to index '{INDEX_NAME}'.")

        # Pinecone's query-by-metadata is complex. A more direct approach is to fetch by ID if we knew them.
        # As a workaround, we'll query with a dummy vector to get a broad set of results and filter them.
        print("Fetching a sample of vectors to check for the document...")
        
        # Query a large number of vectors to ensure we find the ones we're looking for.
        # This is not efficient for large indexes, but works for verification purposes.
        response = index.query(vector=[0.0]*384, top_k=10000, include_metadata=True)
        
        matching_vectors = []
        all_sources_sample = set() # For debugging
        if response and response.get('matches'):
            for match in response['matches']:
                source_metadata = match.metadata.get('source', '').replace("\\", "/")
                if len(all_sources_sample) < 5: # Get a sample of 5 sources
                    all_sources_sample.add(source_metadata)

                if doc_name in source_metadata:
                    matching_vectors.append(match)

        if not matching_vectors:
            print(f"\n--- No vectors found for document: {doc_name} ---")
            print("Please ensure that:")
            print("1. The document name and path are correct.")
            print("2. You have run the `store_index.py` script after adding the document.")
            if all_sources_sample:
                print("\n--- Sample of source paths found in the index ---")
                for sample in all_sources_sample:
                    print(f"  - {sample}")
            return

        print(f"\n--- Found {len(matching_vectors)} vectors for: {doc_name} ---")
        for i, vec in enumerate(matching_vectors):
            print(f"\n--- Vector {i+1} ---")
            print(f"  ID: {vec.id}")
            # The text content is stored in the 'text' field of the metadata
            if 'text' in vec.metadata:
                print(f"  Content Snippet: {vec.metadata['text'][:200]}...")
            else:
                print("  Content Snippet: Not available in metadata.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    check_document_vectors(DOCUMENT_NAME)
