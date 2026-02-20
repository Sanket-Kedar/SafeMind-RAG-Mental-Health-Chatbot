from fastapi import FastAPI, Request, HTTPException, Depends, status, Form
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
import uvicorn
import json
import re
import uuid
import sys
import traceback
import time
import os
from typing import Optional, List
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# LangChain Imports
from src.helper import download_hugging_face_embeddings
from langchain_pinecone import PineconeVectorStore
from langchain_community.chat_models import ChatOllama
from langchain.chains import create_retrieval_chain, create_history_aware_retriever
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

import database as db

# --- Initialization ---
print("Starting SafeMind initialization...", file=sys.stderr)

print("Loading environment variables...", file=sys.stderr)
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    print("ERROR: SECRET_KEY not found in .env file!", file=sys.stderr)
    sys.exit(1)

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
if not PINECONE_API_KEY:
    print("ERROR: PINECONE_API_KEY not found in .env file!", file=sys.stderr)
    sys.exit(1)
os.environ["PINECONE_API_KEY"] = PINECONE_API_KEY

# Initialize database
print("Initializing database...", file=sys.stderr)
db.init_database()

# Initialize FastAPI app
app = FastAPI(title="SafeMind Mental Health Chatbot")

# Middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Load Embeddings & Pinecone
print("Loading embeddings...", file=sys.stderr)
try:
    embeddings = download_hugging_face_embeddings()
    print("✓ Embeddings loaded", file=sys.stderr)
except Exception as e:
    print(f"ERROR loading embeddings: {str(e)}", file=sys.stderr)
    sys.exit(1)

print("Connecting to Pinecone...", file=sys.stderr)
try:
    index_name = "mental-health-chatbot"
    docsearch = PineconeVectorStore.from_existing_index(
        index_name=index_name,
        embedding=embeddings
    )
    print("✓ Pinecone connected", file=sys.stderr)
except Exception as e:
    print(f"ERROR connecting to Pinecone: {str(e)}", file=sys.stderr)
    print("Make sure your Pinecone index 'mental-health-chatbot' exists!", file=sys.stderr)
    sys.exit(1)

print("Initializing retriever...", file=sys.stderr)
retriever = docsearch.as_retriever(search_type="similarity", search_kwargs={"k": 5})
print("✓ Retriever initialized", file=sys.stderr)

print("Initializing ChatOllama...", file=sys.stderr)
# Make sure ollama is running and the model is downloaded
chatModel = ChatOllama(model="llama3.2:1b") 
print("✓ Chat model initialized", file=sys.stderr)

print("SafeMind initialization complete!", file=sys.stderr)


# --- Helper Functions ---

def get_system_prompt(age, gender, location, name):
    """Generate system prompt with user context"""
    name_text = name if name else "User"
    location_text = location if location else "Not specified"

    system_text = (
        "You are SafeMind — a warm, empathetic, and intelligent mental wellbeing assistant. "
        "Your purpose is to help users through emotional support and practical guidance. "
        "USER CONTEXT: "
        f"Name: {name_text}, Age: {age}, Gender: {gender}, Location: {location_text} "
        "Analyze what the user needs: "
        "1. EMOTIONAL - Provide empathy, validation, reassurance, coping strategies "
        "2. TECHNICAL/PRACTICAL - Provide step-by-step solutions and actionable strategies "
        "3. ADVICE - Present multiple perspectives, pros/cons, help clarify values "
        "4. STRESS - Validate pressure while breaking problems in manageable steps "
        "5. WELLNESS - Provide evidence-based health recommendations and stress factors "
        "6. VENTING - Listen empathetically, validate, normalize; don't over-solve "
        "TONE: Always validate first, match their energy, use specific examples, balance comfort with action. "
        "Be warm but effective. If serious mental health crisis, suggest professional help. "
    )
    return system_text, ""

def analyze_user_intent(message):
    """Analyze user message to determine intent and sentiment"""
    message_lower = message.lower()

    emotional_keywords = [
        'feel', 'feeling', 'sad', 'depressed', 'anxious', 'worried', 'stress', 'stressed',
        'overwhelmed', 'scared', 'afraid', 'lonely', 'struggling', 'broken', 'hurt',
        'angry', 'frustrated', 'disappointed', 'devastated', 'heartbroken', 'numb', 'empty',
        'suicidal', 'harm', 'hurt myself', "can't take it", "can't handle", 'breaking down',
        'panic', 'panicking', 'crying', 'cry', 'exhausted', 'tired', 'depressing', 'terrible'
    ]

    technical_keywords = [
        'how to', 'how do i', 'help me', 'can you explain', 'debug', 'code', 'error',
        'problem', 'issue', 'fix', 'solution', 'advice on', 'tips for', 'steps', 'process',
        'way to', 'method', 'technique', 'approach', 'strategy', 'algorithm', 'implement',
        'build', 'create', 'develop', 'learn', 'study', 'understand'
    ]

    knowledge_keywords = [
        'what is', 'what are', 'who is', 'who are', 'explain', 'tell me about', 'define'
    ]

    venting_keywords = [
        'just', 'ugh', 'i hate', 'seriously', 'honestly', 'actually', 'literally',
        'can you imagine', 'no joke', 'can you believe', 'i mean', 'so annoying', 'ridiculous'
    ]

    social_keywords = [
        'hi', 'hello', 'hey', 'greetings', 'morning', 'afternoon', 'evening',
        'how are you', 'how are things', 'how is used', 'whats up', "what's up",
        'ok', 'okay', 'cool', 'nice', 'great', 'thanks', 'thank you', 'thx', 'got it', 'sure'
    ]
    
    urgent_keywords = [
        'crisis', 'emergency', 'immediate', 'right now', 'asap', 'urgent', 'please help',
        'dying', 'dead', 'kill myself', 'end it', 'give up', 'hopeless', 'no point'
    ]

    emotional_count = sum(1 for kw in emotional_keywords if kw in message_lower)
    technical_count = sum(1 for kw in technical_keywords if kw in message_lower)
    venting_count = sum(1 for kw in venting_keywords if kw in message_lower)
    urgent_count = sum(1 for kw in urgent_keywords if kw in message_lower)
    knowledge_count = sum(1 for kw in knowledge_keywords if message_lower.startswith(kw))
    
    # Check for social intent: Short message + social keywords + NO distress indicators
    is_short = len(message.split()) <= 10  # Max 10 words for social check
    has_social_kw = any(kw in message_lower for kw in social_keywords)
    no_distress = emotional_count == 0 and urgent_count == 0 and technical_count == 0
    
    # Priority order for intent detection
    if urgent_count > 0:
        intent = 'emergency'
    elif has_social_kw and is_short and no_distress:
        intent = 'social'
    elif knowledge_count > 0:
        intent = 'knowledge'
    elif technical_count > emotional_count and technical_count > 0:
        intent = 'technical'
    elif emotional_count > technical_count and emotional_count > 0:
        intent = 'emotional'
    elif 'advice' in message_lower or 'should i' in message_lower:
        intent = 'advice'
    elif any(kw in message_lower for kw in ['sleep', 'exercise', 'eat', 'diet', 'fitness']):
        intent = 'wellness'
    else:
        intent = 'venting' # Default to venting if no other intent is detected

    negative_indicators = ['not', 'no', "can't", "don't", "won't", 'fail', 'bad']
    negative_count = sum(1 for ind in negative_indicators if ind in message_lower)

    if urgent_count > 0:
        sentiment = 'urgent'
    elif emotional_count > 3 and negative_count > 0:
        sentiment = 'negative'
    elif any(pos in message_lower for pos in ['great', 'good', 'happy', 'better', 'amazing']):
        sentiment = 'positive'
    else:
        sentiment = 'neutral'

    emotional_level = 'low'
    if urgent_count > 0:
        emotional_level = 'high'
    elif emotional_count > 3:
        emotional_level = 'high'
    elif emotional_count > 1:
        emotional_level = 'medium'

    return {
        'intent': intent,
        'sentiment': sentiment,
        'emotional_level': emotional_level
    }

# --- Pydantic Models ---
class SignupModel(BaseModel):
    email: str
    password: str
    name: str
    age: str
    location: str
    gender: str

class LoginModel(BaseModel):
    email: str
    password: str

class CreateChatModel(BaseModel):
    pass # No params needed for now

# --- Dependencies ---
def get_current_user(request: Request):
    user_id = request.session.get('user_id')
    if not user_id or not request.session.get('authenticated'):
        raise HTTPException(status_code=401, detail="User not authenticated")
    return user_id

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})

@app.post("/signup")
async def signup(data: SignupModel, request: Request):
    try:
        email = data.email.strip().lower()
        password = data.password
        name = data.name.strip()
        age = data.age
        location = data.location.strip()
        gender = data.gender

        # Validation
        if not all([email, password, name, age, location, gender]):
            return JSONResponse({"success": False, "message": "All fields are required"}, status_code=400)

        # Email validation
        email_regex = r'^[^@]+@[^@]+\.[^@]+$'
        if not re.match(email_regex, email):
            return JSONResponse({"success": False, "message": "Invalid email format"}, status_code=400)

        # Password validation
        if len(password) < 8:
            return JSONResponse({"success": False, "message": "Password must be at least 8 characters"}, status_code=400)

        # Age validation
        try:
            age_int = int(age)
            if age_int < 13 or age_int > 120:
                return JSONResponse({"success": False, "message": "Age must be between 13 and 120"}, status_code=400)
        except:
            return JSONResponse({"success": False, "message": "Invalid age"}, status_code=400)

        # Check if user exists
        if db.get_user_by_email(email):
            return JSONResponse({"success": False, "message": "Email already registered"}, status_code=400)

        # Hash password
        password_hash = generate_password_hash(password, method='pbkdf2:sha256')

        # Create user
        user_id = db.create_user(email, name, age, location, gender, password_hash)
        
        if not user_id:
            return JSONResponse({"success": False, "message": "Failed to create user"}, status_code=500)

        # Set session
        request.session['user_id'] = user_id
        request.session['user_name'] = name
        request.session['user_age'] = age
        request.session['user_gender'] = gender
        request.session['user_location'] = location
        request.session['authenticated'] = True

        # Create initial chat
        chat_id = str(uuid.uuid4())
        db.create_chat(chat_id, user_id, 'New Conversation')

        return {
            "success": True,
            "message": "Account created successfully",
            "chat_id": chat_id,
            "user_id": user_id
        }
    except Exception as e:
        print(f"Signup error: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@app.post("/login")
async def login(data: LoginModel, request: Request):
    try:
        email = data.email.strip().lower()
        password = data.password

        if not email or not password:
            return JSONResponse({"success": False, "message": "Email and password required"}, status_code=400)

        # Get user
        user = db.get_user_by_email(email)
        if not user:
            return JSONResponse({"success": False, "message": "Invalid email or password"}, status_code=401)

        # Check password
        if not check_password_hash(user['password_hash'], password):
            return JSONResponse({"success": False, "message": "Invalid email or password"}, status_code=401)

        # Set session
        request.session['user_id'] = user['id']
        request.session['user_name'] = user['name']
        request.session['user_age'] = user['age']
        request.session['user_gender'] = user['gender']
        request.session['user_location'] = user['location']
        request.session['authenticated'] = True

        # Get user's chats
        chats = db.get_user_chats(user['id'])
        
        # Get or create a chat
        if chats:
            chat_id = chats[0]['id']
        else:
            chat_id = str(uuid.uuid4())
            db.create_chat(chat_id, user['id'], 'New Conversation')

        return {
            "success": True,
            "message": "Login successful",
            "chat_id": chat_id,
            "user_id": user['id']
        }
    except Exception as e:
        print(f"Login error: {str(e)}", file=sys.stderr)
        traceback.print_exc()
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

@app.get("/chats")
async def get_chats(request: Request):
    """Get list of chats for current user"""
    try:
        user_id = get_current_user(request)
    except HTTPException as e:
         return JSONResponse({"success": False, "message": e.detail}, status_code=e.status_code)
    
    # Get chats from database
    chats = db.get_user_chats(user_id)
    user_chats = [
        {
            'id': chat['id'],
            'title': chat['title'],
            'timestamp': chat['created_at']
        }
        for chat in chats
    ]
    
    # Return user info along with chats to sync frontend
    return {
        "success": True, 
        "chats": user_chats,
        "user_profile": {
            "name": request.session.get('user_name', 'User'),
            "age": request.session.get('user_age', ''),
            "gender": request.session.get('user_gender', '')
        }
    }

@app.post("/chats")
async def create_chat(request: Request):
    """Create a new chat"""
    try:
        user_id = get_current_user(request)
    except HTTPException as e:
         return JSONResponse({"success": False, "message": e.detail}, status_code=e.status_code)

    chat_id = str(uuid.uuid4())
    
    # Create chat in database
    db.create_chat(chat_id, user_id, 'New Chat')
    
    return {"success": True, "chat_id": chat_id}

@app.delete("/chats/{chat_id}")
async def delete_chat(chat_id: str, request: Request):
    """Delete a chat and all its messages"""
    try:
        user_id = get_current_user(request)
    except HTTPException as e:
         return JSONResponse({"success": False, "message": e.detail}, status_code=e.status_code)
    
    # Verify chat belongs to user
    chat = db.get_chat_by_id(chat_id)
    if not chat or chat['user_id'] != user_id:
        return JSONResponse({"success": False, "message": "Chat not found"}, status_code=404)
    
    # Delete chat and messages from database
    try:
        conn = db.get_db_connection()
        cursor = conn.cursor()
        
        # Delete messages first (foreign key constraint)
        cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        
        # Delete chat
        cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "Chat deleted"}
    except Exception as e:
        print(f"Error deleting chat: {str(e)}", file=sys.stderr)
        return JSONResponse({"success": False, "message": "Failed to delete chat"}, status_code=500)

@app.get("/chats/{chat_id}")
async def get_chat_history(chat_id: str, request: Request):
    """Get messages for a specific chat"""
    try:
        user_id = get_current_user(request)
    except HTTPException as e:
         return JSONResponse({"success": False, "message": e.detail}, status_code=e.status_code)
    
    # Get chat from database and verify ownership
    chat = db.get_chat_by_id(chat_id)
    if not chat or chat['user_id'] != user_id:
        return JSONResponse({"success": False, "message": "Chat not found"}, status_code=404)
    
    # Get messages from database
    messages = db.get_chat_messages(chat_id)
    message_list = [
        {
            'role': msg['role'],
            'content': msg['content']
        }
        for msg in messages
    ]
        
    return {
        "success": True, 
        "messages": message_list
    }

@app.post("/get")
async def chat(request: Request, msg: str = Form(...), chat_id: str = Form(...)):
    """Handle chat messages with sentiment analysis and context-aware responses (Streaming)"""
    try:
        if not request.session.get('authenticated'):
            return JSONResponse({"success": False, "message": "Please login first"}, status_code=400)

        user_id = request.session.get('user_id')
        age = request.session.get('user_age')
        gender = request.session.get('user_gender')
        location = request.session.get('user_location', '')
        name = request.session.get('user_name', '')
        
        if not chat_id:
            print("ERROR: Chat ID string is missing", file=sys.stderr)
            return JSONResponse({"success": False, "message": "Chat ID required"}, status_code=400)

        # Verify chat exists and belongs to user
        chat = db.get_chat_by_id(chat_id)
        if not chat or chat['user_id'] != user_id:
            print(f"ERROR: Chat {chat_id} not found or unauthorized for user {user_id}", file=sys.stderr)
            return JSONResponse({"success": False, "message": "Chat not found"}, status_code=404)
       
        # Load chat history from database
        messages = db.get_chat_messages(chat_id)
        
        # Update title if first message
        if not messages:
            title_words = msg.split()[:5]
            new_title = " ".join(title_words) + "..."
            db.update_chat_title(chat_id, new_title)
        
        # Convert history to LangChain message objects
        langchain_history = []
        for message in messages:
            if message['role'] == 'user':
                langchain_history.append(HumanMessage(content=message['content']))
            elif message['role'] == 'assistant' or message['role'] == 'bot':
                langchain_history.append(AIMessage(content=message['content']))

        # Streaming Generator Function
        async def generate():
            full_response = ""
            
            # Step 1: Analyze Intent
            yield json.dumps({"type": "status", "content": "Analyzing intent..."}) + "\n"
            # time.sleep(0.5) # Blocking sleep in async function is bad, but for short duration/UX it's acceptable or use asyncio.sleep
            import asyncio
            await asyncio.sleep(0.5)

            t_start_intent = time.time()
            analysis = analyze_user_intent(msg)
            print(f"[TIMING] Intent Analysis took: {time.time() - t_start_intent:.4f}s", file=sys.stderr)
            
            # Formulate System Prompt
            system_prompt_text, cot_instruction = get_system_prompt(age, gender, location, name)
            intent_upper = analysis['intent'].upper()
            sentiment = analysis['sentiment']
            emotional_level = analysis['emotional_level']
            
            # Emergency Crisis Handling - Inject Resources FIRST
            if analysis['intent'] == 'emergency':
                print(f"🚨 EMERGENCY INTENT DETECTED for user in {location}", file=sys.stderr)
                
                # Now let LLM provide empathetic follow-up
                is_india = location and any(kw in location.lower() for kw in ['india', 'delhi', 'mumbai', 'bangalore', 'pune', 'chennai', 'kolkata', 'hyderabad'])
                
                india_instructions = ""
                if is_india:
                    india_instructions = (
                        "SPECIFIC FOR INDIA: You MUST mention 'Tele MANAS', the verified 24/7 national mental health helpline. "
                        "The number is 14416 or 1-800-891-4416. Website: https://telemanas.mohfw.gov.in/home "
                        "Urge them to call this free service immediately. "
                    )

                crisis_system_prompt = (
                    "You are SafeMind, a compassionate mental health assistant. "
                    "The user is experiencing a crisis. "
                    "Your role is to provide warm, empathetic support and suggest professional help. "
                    "Validate their feelings, remind them they are not alone, and gently encourage them to reach out for help. "
                    f"Provide specific crisis resources or emergency numbers relevant to their location {location}. "
                    f"{india_instructions}"
                    "Keep your response warm and hopeful. "
                    f"\nUser Name: {name}, Location: {location}"
                )
                
                crisis_prompt = ChatPromptTemplate.from_messages([
                    ("system", crisis_system_prompt),
                    MessagesPlaceholder("chat_history"),
                    ("human", "{input}"),
                ])
                
                chain = crisis_prompt | chatModel
                async for chunk in chain.astream({"input": msg, "chat_history": langchain_history}):
                    content = chunk.content
                    full_response += content
                    yield json.dumps({"type": "token", "content": content}) + "\n"
                    # await asyncio.sleep(0) # Yield control
                
                # Done handling emergency
            
            # Fast Path for Social Intent
            elif analysis['intent'] == 'social':
                # Simplified social prompt
                social_system_prompt = (
                    "You are a friendly, warm conversational assistant. "
                    "The user has sent a casual social message. "
                    "Respond instantly with a short, friendly reply (1-2 lines maximum). "
                    "Do NOT analyze emotions. Do NOT give advice. Do NOT be clinical. "
                    "Just be human and natural."
                    f"\nUser Name: {name}"
                )
                
                social_prompt = ChatPromptTemplate.from_messages([
                    ("system", social_system_prompt),
                    ("human", "{input}"),
                ])
                
                chain = social_prompt | chatModel
                async for chunk in chain.astream({"input": msg}):
                    content = chunk.content
                    full_response += content
                    yield json.dumps({"type": "token", "content": content}) + "\n"
                    
                # Done handling social
            
            else:
                intent_context = (
                    f"[Context: Intent={intent_upper}, Sentiment={sentiment}, Emotion={emotional_level}]"
                )

                non_retrieval_intents = ['venting', 'emotional']
                
                if analysis['intent'] in non_retrieval_intents:
                    # Conversational Chain
                    conversational_system_prompt = f"""{system_prompt_text}
{intent_context}"""
                    
                    conversational_prompt = ChatPromptTemplate.from_messages([
                        ("system", conversational_system_prompt),
                        MessagesPlaceholder("chat_history"),
                        ("human", "{input}"),
                    ])
                    
                    chain = conversational_prompt | chatModel
                    
                    # Stream the response
                    async for chunk in chain.astream({"input": msg, "chat_history": langchain_history}):
                        content = chunk.content
                        full_response += content
                        yield json.dumps({"type": "token", "content": content}) + "\n"
                        
                else:
                    # RAG Chain in Manual Steps for transparency and score logging
                    
                    rephrased_msg = msg
                    
                    # 2. Retrieve with Scores
                    # docsearch is the PineconeVectorStore instance
                    yield json.dumps({"type": "status", "content": "Searching knowledge base..."}) + "\n"
                    t_start_retrieve = time.time()
                    docs_and_scores = docsearch.similarity_search_with_score(rephrased_msg, k=5)
                    print(f"[TIMING] Vector Retrieval took: {time.time() - t_start_retrieve:.4f}s", file=sys.stderr)
                    
                    # 3. Log RAG Details to Terminal (Backend Only)
                    print("\n" + "="*50, file=sys.stderr)
                    print("===== RAG RETRIEVAL START =====", file=sys.stderr)
                    print(f"Query: {msg}", file=sys.stderr)
                    print(f"Intent={intent_upper} | Sentiment={sentiment} | Emotion={emotional_level}", file=sys.stderr)
                    
                    total_score = 0
                    retrieved_docs = []
                    
                    for i, (doc, score) in enumerate(docs_and_scores):
                        source = doc.metadata.get('source', 'Unknown source')
                        # Preview content safely
                        preview = doc.page_content.strip().replace('\n', ' ')[:150]
                        print(f"[Doc {i+1}] Source={source} | Score={score:.4f} | Preview=\"{preview}...\"", file=sys.stderr)
                        
                        retrieved_docs.append(doc)
                    
                    # 4. Compute Confidence Score
                    # Use MAX score (best match) rather than average, as one good doc is enough.
                    confidence_score = 0.0
                    if docs_and_scores:
                        # Assuming sorted, but max() is safer
                        confidence_score = max(score for doc, score in docs_and_scores)
                    
                    print(f"RAG Confidence Score (Max): {confidence_score:.4f}", file=sys.stderr)
                    print("===== RAG RETRIEVAL END =====", file=sys.stderr)
                    print("="*50 + "\n", file=sys.stderr)
                    
                    # 5. Low Confidence Handling
                    confidence_warning = ""
                    if confidence_score < 0.35:
                        print("!!! WARNING: Low RAG Confidence. Applying conservative constraints.", file=sys.stderr)
                        confidence_warning = (
                            "\nWARNING: The retrieved context has low relevance confidence. "
                            "Do NOT make strong medical claims or factual assertions unless strictly supported by the context. "
                            "Use guarded language (e.g., 'The guidelines suggest...', 'It may be helpful to...'). "
                            "If the answer is not in the context, admit it politely."
                        )

                    # 6. Generate Response (Streaming)
                    # Create Stuff Documents Chain manually to stream response
                    full_system_prompt = f"""{system_prompt_text}
{intent_context}
{confidence_warning}
Context from knowledge base:
{{context}}"""

                    qa_prompt = ChatPromptTemplate.from_messages([
                        ("system", full_system_prompt),
                        MessagesPlaceholder("chat_history"),
                        ("human", "{input}"),
                    ])
                    
                    question_answer_chain = create_stuff_documents_chain(chatModel, qa_prompt)
                    
                    # We invoke/stream the chain with the retrieves docs directly
                    async for chunk in question_answer_chain.astream({
                        "input": msg, 
                        "chat_history": langchain_history,
                        "context": retrieved_docs
                    }):
                        content = chunk # stuff chain yields string chunks directly usually
                        
                        if hasattr(chunk, 'content'):
                            content = chunk.content
                        else:
                            content = str(chunk)
                            
                        full_response += content
                        yield json.dumps({"type": "token", "content": content}) + "\n"
            
            # Completion
            # Save messages to database
            db.add_message(chat_id, 'user', msg)
            db.add_message(chat_id, 'assistant', full_response)
            
            yield json.dumps({"type": "done"}) + "\n"

        return StreamingResponse(generate(), media_type='application/x-ndjson')

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return JSONResponse({"success": False, "message": str(e)}, status_code=500)

if __name__ == '__main__':
    print("Open your browser and go to: localhost:8080", file=sys.stderr)
    uvicorn.run(app, host="0.0.0.0", port=8080)