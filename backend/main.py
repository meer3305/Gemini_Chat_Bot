import os
from typing import Optional, List
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from fastapi import FastAPI


from supabase import create_client, Client
import google.generativeai as genai

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS","*").split(",")

if not (SUPABASE_URL and SUPABASE_SERVICE_KEY and GEMINI_API_KEY):
    raise RuntimeError("Missing env vars for Supabase/Gemini")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def root():
    return {"message": "✅ Gemini Chatbot Backend is running!"}


# ---------- Models ----------
class StartConversationReq(BaseModel):
    title: Optional[str] = None

class ChatReq(BaseModel):
    conversation_id: str
    message: str

class ChatResp(BaseModel):
    reply: str

# ---------- Auth helper ----------
async def get_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    Expect header: Authorization: Bearer <supabase_access_token_from_frontend>
    Validate token and return the Supabase user id.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]

    try:
        # supabase-py may return different shapes depending on version.
        # Support both object-like and dict-like responses.
        resp = supabase.auth.get_user(token)

        # Try object attribute first
        user_obj = None
        if hasattr(resp, "user") and resp.user:
            user_obj = resp.user
        elif isinstance(resp, dict):
            # Some versions return {"data": {"user": {...}}}
            user_obj = resp.get("data", {}).get("user") or resp.get("user")

        if not user_obj:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Extract id whether dict or object
        if isinstance(user_obj, dict):
            user_id = user_obj.get("id")
        else:
            user_id = getattr(user_obj, "id", None)

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        return user_id
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# ---------- Routes ----------
@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/start-conversation")
async def start_conversation(payload: StartConversationReq, user_id: str = Depends(get_user_id)):
    title = payload.title or "New Conversation"
    conv = supabase.table("conversations").insert({"user_id": user_id, "title": title}).execute()

    # Normalize response shape
    conv_data = getattr(conv, "data", None) or []
    if isinstance(conv_data, list) and conv_data:
        conv_id = conv_data[0].get("id")
    elif isinstance(conv_data, dict):
        conv_id = conv_data.get("id")
    else:
        conv_id = None

    if not conv_id:
        raise HTTPException(status_code=500, detail="Failed to create conversation")

    return {"conversation_id": conv_id}

@app.get("/history/{conversation_id}")
async def history(conversation_id: str, user_id: str = Depends(get_user_id)):
    # Verify conversation belongs to user (RLS will also enforce)
    conv = supabase.table("conversations").select("*").eq("id", conversation_id).single().execute()
    conv_data = getattr(conv, "data", None)
    if not conv_data or (isinstance(conv_data, dict) and conv_data.get("user_id") != user_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = (
        supabase.table("chat_messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .order("created_at", desc=False)
        .execute()
    )
    return {"messages": getattr(msgs, "data", []) or []}

@app.post("/chat", response_model=ChatResp)
async def chat(payload: ChatReq, user_id: str = Depends(get_user_id)):
    # Get recent history (optional context)
    history_resp = (
        supabase.table("chat_messages")
        .select("role, content")
        .eq("conversation_id", payload.conversation_id)
        .order("created_at", desc=False)
        .limit(20)
        .execute()
    )
    history = getattr(history_resp, "data", []) or []

    user_msg = (payload.message or "").strip()

    # Build prompt with short history
    parts: List[str] = []
    for h in history[-8:]:  # last 8 messages for brevity
        # defensive extraction
        role = h.get("role") if isinstance(h, dict) else getattr(h, "role", "")
        content = h.get("content") if isinstance(h, dict) else getattr(h, "content", "")
        parts.append(f"{role.upper()}: {content}")
    parts.append(f"USER: {user_msg}")
    prompt = "\n".join(parts)

    # Call Gemini safely — if the library or API fails, return a friendly fallback.
    reply_text = "Sorry, I couldn't generate a response right now."
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        # generate_content can vary by version; attempt common access patterns
        result = model.generate_content(prompt)
        # result may hold text in different attributes
        reply_text = getattr(result, "text", None) or getattr(result, "content", None) or str(result)
    except Exception:
        # keep fallback reply_text
        pass

    # Persist both user and assistant messages (best-effort; don't fail the request on DB errors)
    try:
        supabase.table("chat_messages").insert([
            {
                "conversation_id": payload.conversation_id,
                "user_id": user_id,
                "role": "user",
                "content": user_msg,
            },
            {
                "conversation_id": payload.conversation_id,
                "user_id": user_id,
                "role": "assistant",
                "content": reply_text,
            }
        ]).execute()
    except Exception:
        # log in real app; here we silently ignore DB persistence failures so the chat still returns
        pass

    return ChatResp(reply=reply_text)
