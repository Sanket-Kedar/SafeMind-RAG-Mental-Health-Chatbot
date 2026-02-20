from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from typing import List
from langchain.schema import Document
import hashlib


def sanitize_text(text: str) -> str:
    """
    Sanitizes text to remove harmful content while preserving helpful information.
    Removes specific keywords related to methods, dosages, and lethality.
    """
    # Define keywords to redact (simple blacklist for safety demonstration)
    # In a real production system, this would be a more sophisticated NLP model
    redact_patterns = [
        "methods of suicide", "suicide method", "ways to kill", "how to hang", 
        "lethal dose", "overdose amount", "cutting veins", "how to cut",
        "specific plan", "buy gun", "buy rope" 
    ]
    
    sanitized_text = text.lower() # Normalize for checking, but we might want to preserve case.
    # Actually, let's keep it simple: case-insensitive replace of phrases with [REDACTED]
    
    text_lower = text.lower()
    for pattern in redact_patterns:
        if pattern in text_lower:
            # Simple redaction - not perfect but satisfies the requirement
            # Using a case-insensitive replacement strategy would be better but keeping it simple for now
            # We will just replace the exact match in the lower case version?? 
            # No, let's just do a naive replace for now or use regex for case insensitive
            import re
            text = re.sub(re.escape(pattern), "[SAFETY REDACTED]", text, flags=re.IGNORECASE)
            
    return text


def load_pdf_file(data_dir, filenames=None):
    """
    Load PDF files. 
    If filenames is provided, only load those specific files.
    Otherwise, load all PDFs in data_dir.
    """
    import os
    all_docs = []
    
    if filenames is None:
        files_to_process = [f for f in os.listdir(data_dir) if f.endswith('.pdf')]
    else:
        files_to_process = [f for f in filenames if f.endswith('.pdf')]
    
    for filename in files_to_process:
        file_path = os.path.join(data_dir, filename)
        print(f"Processing file: {filename}", flush=True)
        try:
            loader = PyPDFLoader(file_path)
            documents = loader.load()
            
            # Apply Sanitization immediately after loading
            for doc in documents:
                doc.page_content = sanitize_text(doc.page_content)
                
            all_docs.extend(documents)
            print(f"  - Loaded and sanitized {len(documents)} pages.", flush=True)
        except Exception as e:
            print(f"  - Error loading file {filename}: {e}", flush=True)
            
    return all_docs



def filter_to_minimal_docs(docs: List[Document]) -> List[Document]:
    minimal_docs: List[Document] = []
    for doc in docs:
        src = doc.metadata.get("source")
        minimal_docs.append(
            Document(
                page_content=doc.page_content,
                metadata={"source": src}
            )
        )
    return minimal_docs



def text_split(extracted_data):
    # text_splitter=RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=20)
    # Optimized for mental health domain: larger chunks preserve clinical context,
    # and 15% overlap ensures continuity of therapeutic concepts across boundaries
    text_splitter=RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    text_chunks=text_splitter.split_documents(extracted_data)
    return text_chunks



def download_hugging_face_embeddings():
    embeddings=HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')
    return embeddings

def generate_chunk_ids(chunks):
    for chunk in chunks:
        chunk_id = hashlib.sha256(f"{chunk.metadata['source']}-{chunk.page_content}".encode()).hexdigest()
        chunk.metadata['id'] = chunk_id
    return chunks