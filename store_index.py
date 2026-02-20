import hashlib
import json
import time
from dotenv import load_dotenv
import os
from src.helper import load_pdf_file, filter_to_minimal_docs, text_split, download_hugging_face_embeddings, generate_chunk_ids
from pinecone import Pinecone
from pinecone import ServerlessSpec 
from langchain_pinecone import PineconeVectorStore

load_dotenv()

PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

DATA_DIR = r"C:\mental-health-chatbot\mental-health-chatbot-main\data"
STATE_FILE = "indexing_state.json"
INDEX_NAME = "mental-health-chatbot"
BATCH_SIZE = 100

def get_file_hash(filepath):
    """Calculate SHA256 hash of a file."""
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def load_state():
    """Load indexing state from JSON file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_state(state):
    """Save indexing state to JSON file."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def main():
    print("--- Starting Data Ingestion ---")
    
    # 1. Initialize Pinecone
    print("Initializing Pinecone...")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    
    if not pc.has_index(INDEX_NAME):
        print(f"Creating index '{INDEX_NAME}'...")
        pc.create_index(
            name=INDEX_NAME,
            dimension=384,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    index = pc.Index(INDEX_NAME)
    print("✓ Pinecone connected")

    # 2. Check for new/modified files
    print("Checking for file changes (Incremental Indexing)...")
    state = load_state()
    current_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.pdf')]
    
    files_to_process = []
    file_hashes = {}  # Store hashes but don't update state yet
    
    for filename in current_files:
        filepath = os.path.join(DATA_DIR, filename)
        file_hash = get_file_hash(filepath)
        
        # Check if file is new or modified
        if filename not in state or state[filename] != file_hash:
            files_to_process.append(filename)
            file_hashes[filename] = file_hash  # Store for later
            print(f"  [+] Found new/modified file: {filename}")
        else:
            print(f"  [.] Skipping unchanged file: {filename}")
            
    if not files_to_process:
        print("No new documents to index.")
        print("--- Data Ingestion Complete ---")
        return

    # 3. Download embedding model once
    print("\nDownloading Embeddings Model...")
    embeddings = download_hugging_face_embeddings()
    docsearch = PineconeVectorStore(index=index, embedding=embeddings)
    
    # 4. Process files ONE AT A TIME
    print(f"\nProcessing {len(files_to_process)} file(s) individually...")
    total_start_time = time.time()
    successful_files = 0
    failed_files = []
    
    for file_idx, filename in enumerate(files_to_process):
        print(f"\n{'='*60}")
        print(f"[{file_idx + 1}/{len(files_to_process)}] Processing: {filename}")
        print(f"{'='*60}")
        
        try:
            # Load and process this single file
            file_start_time = time.time()
            extracted_data = load_pdf_file(data_dir=DATA_DIR, filenames=[filename])
            
            if not extracted_data:
                print(f"  ⚠️  No content extracted from {filename}, skipping...")
                failed_files.append((filename, "No content extracted"))
                continue
            
            filter_data = filter_to_minimal_docs(extracted_data)
            text_chunks = text_split(filter_data)
            print(f"  Generated {len(text_chunks)} chunks from {len(extracted_data)} pages")
            
            text_chunks_with_ids = generate_chunk_ids(text_chunks)
            
            # Batch upsert for this file
            total_chunks = len(text_chunks_with_ids)
            print(f"  Upserting {total_chunks} chunks in batches of {BATCH_SIZE}...")
            
            for i in range(0, total_chunks, BATCH_SIZE):
                batch = text_chunks_with_ids[i : i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1
                total_batches = (total_chunks + BATCH_SIZE - 1) // BATCH_SIZE
                print(f"    Batch {batch_num}/{total_batches} ({len(batch)} chunks)...", end=" ", flush=True)
                
                try:
                    docsearch.add_documents(
                        documents=batch,
                        ids=[chunk.metadata['id'] for chunk in batch]
                    )
                    print("✓")
                except Exception as e:
                    print(f"✗ ERROR: {e}")
                    raise  # Re-raise to trigger file-level error handling
            
            # SUCCESS - Save state for this file immediately
            state[filename] = file_hashes[filename]
            save_state(state)
            
            file_time = time.time() - file_start_time
            successful_files += 1
            print(f"  ✅ Successfully indexed {filename} in {file_time:.2f}s")
            print(f"  ✓ State updated for this file")
            
        except Exception as e:
            print(f"  ❌ FAILED to index {filename}: {e}")
            failed_files.append((filename, str(e)))
            print(f"  ⚠️  Continuing with next file...")
            continue

    # 5. Summary
    total_time = time.time() - total_start_time
    print(f"\n{'='*60}")
    print(f"--- Data Ingestion Complete in {total_time:.2f}s ---")
    print(f"✅ Successfully indexed: {successful_files}/{len(files_to_process)} files")
    
    if failed_files:
        print(f"\n❌ Failed files ({len(failed_files)}):")
        for fname, error in failed_files:
            print(f"  - {fname}: {error}")
        # print("\n💡 Tip: Re-run the script to retry failed files.")

if __name__ == "__main__":
    main()