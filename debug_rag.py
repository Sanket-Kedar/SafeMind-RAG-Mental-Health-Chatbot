import os
import sys
from dotenv import load_dotenv
from langchain_pinecone import PineconeVectorStore
from langchain_community.chat_models import ChatOllama
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage
from src.helper import download_hugging_face_embeddings
import json

# Setup logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_rag():
    print("Loading info...")
    load_dotenv()
    
    # 1. Embeddings
    print("Loading embeddings...")
    try:
        embeddings = download_hugging_face_embeddings()
        print("Embeddings loaded.")
    except Exception as e:
        print(f"Error loading embeddings: {e}")
        return

    # 2. Pinecone
    print("Connecting to Pinecone...")
    try:
        index_name = "mental-health-chatbot"
        # Check API key
        if not os.getenv("PINECONE_API_KEY"):
            print("PINECONE_API_KEY not found.")
            return
            
        docsearch = PineconeVectorStore.from_existing_index(
            index_name=index_name,
            embedding=embeddings
        )
        print("Pinecone connected.")
    except Exception as e:
        print(f"Error connecting to Pinecone: {e}")
        return

    # 3. ChatOllama
    print("Initializing ChatOllama...")
    try:
        chatModel = ChatOllama(model="llama3.2:1b")
        # Test basic invocation
        print("Testing basic LLM invocation...")
        resp = chatModel.invoke("Hello")
        print(f"LLM Response: {resp.content}")
    except Exception as e:
        print(f"Error initializing/invoking ChatOllama: {e}")
        return

    # 4. Retrieval
    query = "what is psychoeducation?"
    print(f"Testing retrieval for: '{query}'")
    try:
        docs_and_scores = docsearch.similarity_search_with_score(query, k=2)
        print(f"Retrieved {len(docs_and_scores)} docs.")
        for i, (doc, score) in enumerate(docs_and_scores):
            print(f"Doc {i} score: {score}")
            print(f"Content: {doc.page_content[:50]}...")
            
        retrieved_docs = [doc for doc, score in docs_and_scores]
    except Exception as e:
        print(f"Error during retrieval: {e}")
        return

    # 5. Chain execution (mimicking app.py)
    print("Testing Chain execution...")
    try:
        system_prompt = "You are a helpful assistant. Use context to answer: {context}"
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        
        question_answer_chain = create_stuff_documents_chain(chatModel, qa_prompt)
        
        print("Streaming response...")
        for chunk in question_answer_chain.stream({
            "input": query, 
            "context": retrieved_docs
        }):
            if hasattr(chunk, 'content'):
                print(chunk.content, end="|", flush=True)
            else:
                print(str(chunk), end="|", flush=True)
        print("\nStream finished.")
        
    except Exception as e:
        print(f"Error during chain execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_rag()
