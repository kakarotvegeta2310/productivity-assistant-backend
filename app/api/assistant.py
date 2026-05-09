from fastapi import APIRouter
from pydantic import BaseModel
import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime

load_dotenv(dotenv_path=".env")
API_KEY = os.getenv("OPENROUTER_API_KEY")

router = APIRouter(prefix="/assistant", tags=["assistant"])

# --- In-memory note storage ---
notes_store: list[str] = []

# --- Tool functions ---
def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def save_note(note: str) -> str:
    notes_store.append(note)
    return f"Note saved: '{note}'"

def get_notes() -> str:
    if not notes_store:
        return "No notes saved yet."
    return "\n".join(f"- {n}" for n in notes_store)

TOOLS = {
    "get_current_time": get_current_time,
    "save_note": save_note,
    "get_notes": get_notes,
}

TOOL_DESCRIPTIONS = """
You have access to these tools. Call them by including a "tool_call" key in your JSON response.

Tools:
- get_current_time() → returns current date and time
- save_note(note: str) → saves a note for the user
- get_notes() → retrieves all saved notes

To call a tool, respond ONLY with:
{
  "tool_call": { "name": "tool_name", "args": { "arg_name": "value" } }
}

If no tool is needed, respond with:
{
  "reply": "your response",
  "tasks": ["task1", "task2"],
  "priority": "low/medium/high"
}
"""

# --- Models ---
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[Message] = []

# --- Route ---
@router.post("/chat")
def chat(req: ChatRequest):
    try:
        if not API_KEY:
            return {"reply": "OPENROUTER_API_KEY is missing.", "actions": [], "history": []}

        messages = []

        # Append conversation history
        for msg in req.history:
            messages.append({"role": msg.role, "content": msg.content})

        # Inject system prompt into first user message
        first_message = f"""You are an AI productivity agent. Always respond ONLY in valid JSON with no extra text.

{TOOL_DESCRIPTIONS}

Rules:
- Always return valid JSON only
- tasks must always be an array, even if empty
- No text outside JSON
- Keep reply clear and useful

User message: {req.message}"""

        messages.append({"role": "user", "content": first_message})

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openrouter/free",
                "messages": messages
            },
            timeout=60,
        )

        data = response.json()
        print("OPENROUTER RESPONSE:", data)

        if response.status_code != 200 or "choices" not in data:
            return {"reply": f"API error: {data}", "actions": [], "history": req.history}

        content = data["choices"][0]["message"]["content"]

        # Strip markdown code fences if present
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        try:
            parsed = json.loads(content)
        except Exception:
            return {
                "reply": content,
                "actions": [],
                "history": req.history + [
                    {"role": "user", "content": req.message},
                    {"role": "assistant", "content": content}
                ]
            }

        # Handle tool call
        if "tool_call" in parsed:
            tool_name = parsed["tool_call"].get("name")
            tool_args = parsed["tool_call"].get("args", {})

            if tool_name in TOOLS:
                tool_fn = TOOLS[tool_name]
                tool_result = tool_fn(**tool_args) if tool_args else tool_fn()
            else:
                tool_result = f"Unknown tool: {tool_name}"

            tool_reply = f"[Tool: {tool_name}] → {tool_result}"

            updated_history = req.history + [
                {"role": "user", "content": req.message},
                {"role": "assistant", "content": tool_reply}
            ]

            return {
                "reply": tool_reply,
                "actions": [],
                "history": updated_history
            }

        # Normal reply
        reply = parsed.get("reply", "")
        tasks = parsed.get("tasks", [])
        priority = parsed.get("priority", "medium")

        updated_history = req.history + [
            {"role": "user", "content": req.message},
            {"role": "assistant", "content": reply}
        ]

        return {
            "reply": reply,
            "actions": tasks,
            "priority": priority,
            "history": updated_history
        }

    except Exception as e:
        return {"reply": f"Error: {str(e)}", "actions": [], "history": req.history}


@router.get("/notes")
def list_notes():
    return {"notes": notes_store}