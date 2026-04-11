"""
whatsapp_bot.py – WhatsApp Cloud API integration for RxAI / BisaRx.

Registers webhook routes on the FastAPI app and handles the full
conversation lifecycle over WhatsApp:  incoming message → triage →
pharmacist handoff → reply.
"""

import hashlib
import hmac
import os
import time
from typing import Any

import httpx
from fastapi import APIRouter, Request, Response, HTTPException

from database import SessionLocal
import chat_engine

# ── config ───────────────────────────────────────────────────────────
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "rxai-verify-token")
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v21.0")

GRAPH_API_BASE = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}"

# Conversation timeout in seconds (30 min)
CONVERSATION_TTL = int(os.getenv("WHATSAPP_CONVERSATION_TTL", "1800"))

router = APIRouter(prefix="/webhook", tags=["whatsapp"])

# ── in‑memory conversation store ────────────────────────────────────
# Key: phone number (str)
# Value: {"messages": [...], "last_active": float}
_conversations: dict[str, dict[str, Any]] = {}


def _get_conversation(phone: str) -> list[dict]:
    """Return the message history for *phone*, resetting if stale."""
    now = time.time()
    entry = _conversations.get(phone)
    if entry and now - entry["last_active"] < CONVERSATION_TTL:
        entry["last_active"] = now
        return entry["messages"]
    # expired or new
    _conversations[phone] = {"messages": [], "last_active": now}
    return _conversations[phone]["messages"]


def _cleanup_stale_conversations():
    """Remove conversations older than TTL (call periodically)."""
    now = time.time()
    stale = [p for p, v in _conversations.items() if now - v["last_active"] >= CONVERSATION_TTL]
    for p in stale:
        del _conversations[p]


# ── WhatsApp Cloud API helpers ──────────────────────────────────────
async def send_text_message(to: str, body: str):
    """Send a plain‑text WhatsApp message."""
    url = f"{GRAPH_API_BASE}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    # WhatsApp has a 4096 char limit per message – split if needed
    chunks = _split_message(body, max_len=4000)
    async with httpx.AsyncClient(timeout=30) as client:
        for chunk in chunks:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": to,
                "type": "text",
                "text": {"preview_url": False, "body": chunk},
            }
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                print(f"[WA] send_text_message error: {resp.status_code} {resp.text}")


async def send_interactive_buttons(to: str, body: str, buttons: list[dict]):
    """
    Send an interactive button message.

    buttons – list of {"id": "...", "title": "..."}  (max 3 buttons, title ≤ 20 chars)
    """
    url = f"{GRAPH_API_BASE}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body[:1024]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"][:20]}}
                    for b in buttons[:3]
                ]
            },
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            print(f"[WA] send_interactive_buttons error: {resp.status_code} {resp.text}")


async def send_interactive_list(to: str, body: str, button_text: str, sections: list[dict]):
    """
    Send an interactive list message.

    sections – [{"title": "...", "rows": [{"id": "...", "title": "...", "description": "..."}]}]
    """
    url = f"{GRAPH_API_BASE}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body[:1024]},
            "action": {
                "button": button_text[:20],
                "sections": sections,
            },
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            print(f"[WA] send_interactive_list error: {resp.status_code} {resp.text}")


async def mark_as_read(message_id: str):
    """Mark a received message as read (blue ticks)."""
    url = f"{GRAPH_API_BASE}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, json=payload, headers=headers)


def _split_message(text: str, max_len: int = 4000) -> list[str]:
    """Split a long message into WhatsApp‑safe chunks."""
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        # try to split at a newline
        cut = text.rfind("\n", 0, max_len)
        if cut < max_len // 2:
            cut = text.rfind(". ", 0, max_len)
        if cut < max_len // 2:
            cut = max_len
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return parts


# ── signature verification ──────────────────────────────────────────
def _verify_signature(payload: bytes, signature_header: str) -> bool:
    """Verify the X-Hub-Signature-256 header from Meta."""
    if not WHATSAPP_APP_SECRET:
        return True  # skip verification in development
    if not signature_header:
        print("[WA] Signature verification failed: X-Hub-Signature-256 header missing")
        return False
    
    expected = "sha256=" + hmac.new(
        WHATSAPP_APP_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    
    match = hmac.compare_digest(expected, signature_header)
    if not match:
        print(f"[WA] Signature mismatch! Expected: {expected}, Received: {signature_header}")
    return match


# ── message extraction ──────────────────────────────────────────────
def _extract_message_text(message: dict) -> str | None:
    """Extract the user‑readable text from any supported message type."""
    msg_type = message.get("type", "")

    if msg_type == "text":
        return (message.get("text") or {}).get("body", "").strip() or None

    if msg_type == "interactive":
        interactive = message.get("interactive") or {}
        itype = interactive.get("type", "")
        if itype == "button_reply":
            return (interactive.get("button_reply") or {}).get("title", "").strip() or None
        if itype == "list_reply":
            return (interactive.get("list_reply") or {}).get("title", "").strip() or None

    if msg_type == "button":
        return (message.get("button") or {}).get("text", "").strip() or None

    # Unsupported types (image, audio, etc.) – ask for text
    return None


# ── webhook routes ──────────────────────────────────────────────────
@router.get("")
async def verify_webhook(request: Request):
    """
    Meta sends GET with hub.mode, hub.verify_token, hub.challenge.
    We respond with the challenge if the token matches.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        print(f"[WA] Webhook verified successfully")
        return Response(content=challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("")
async def handle_webhook(request: Request):
    """
    Receives incoming WhatsApp messages and status updates from Meta.
    Must return 200 quickly – heavy processing is done inline for
    simplicity (acceptable for moderate traffic).
    """
    body = await request.body()
    data = await request.json()
    print("====================================", flush=True)
    print(f"[[WEBHOOK RECEIVED]]: {data}", flush=True)
    print("====================================", flush=True)

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = await request.json()

    # Extract messages from the webhook payload
    try:
        entries = data.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})

                # Handle status updates (delivered, read, etc.) – just acknowledge
                if "statuses" in value:
                    continue

                messages = value.get("messages", [])
                for message in messages:
                    await _process_incoming_message(message, value)
    except Exception as exc:
        print(f"[WA] Error processing webhook: {exc}")

    # Always return 200 quickly
    return Response(status_code=200)


# ── message processing ──────────────────────────────────────────────
# Welcome / greeting keywords
_GREETING_KEYWORDS = {"hi", "hello", "hey", "good morning", "good afternoon",
                       "good evening", "start", "menu", "help", "helo"}

_WELCOME_MESSAGE = (
    "👋 *Welcome to BisaRx!*\n\n"
    "I'm your clinical care assistant. I can help you:\n\n"
    "🩺 Describe your symptoms and get guidance\n"
    "💊 Get your case reviewed by a licensed pharmacist\n"
    "🌍 Communicate in English or Twi\n\n"
    "Simply tell me how you're feeling, and I'll guide you step by step."
)

_UNSUPPORTED_TYPE_MESSAGE = (
    "I can only read text messages for now. "
    "Please describe your symptoms in words and I'll help you. 🙏"
)


async def _process_incoming_message(message: dict, value: dict):
    """Handle a single incoming WhatsApp message."""
    sender = message.get("from", "")  # phone number in international format
    message_id = message.get("id", "")

    if not sender:
        return

    # Mark as read (blue ticks)
    await mark_as_read(message_id)

    # Extract text
    text = _extract_message_text(message)

    if text is None:
        await send_text_message(sender, _UNSUPPORTED_TYPE_MESSAGE)
        return

    # Handle greetings / reset
    if text.lower().strip() in _GREETING_KEYWORDS or text.lower().strip() == "reset":
        # Reset conversation on greeting
        _conversations.pop(sender, None)
        if text.lower().strip() == "reset":
            await send_text_message(sender, "🔄 Conversation reset. How can I help you today?")
            return
        await send_interactive_buttons(
            to=sender,
            body=_WELCOME_MESSAGE,
            buttons=[
                {"id": "btn_symptoms", "title": "Describe Symptoms"},
                {"id": "btn_emergency", "title": "Emergency Help"},
                {"id": "btn_info", "title": "About BisaRx"},
            ],
        )
        return

    # Handle button responses
    if text == "Describe Symptoms":
        await send_text_message(
            sender,
            "Please tell me what symptoms you're experiencing. "
            "For example: _I have a headache and fever since yesterday._"
        )
        return

    if text == "Emergency Help":
        await send_text_message(
            sender,
            "🚨 *Emergency Guidance*\n\n"
            "If you or someone near you has:\n"
            "• Difficulty breathing\n"
            "• Chest pain\n"
            "• Convulsions or seizures\n"
            "• Severe bleeding\n"
            "• Loss of consciousness\n\n"
            "👉 *Please call 112 or go to the nearest hospital immediately.*\n\n"
            "If it's not an emergency, describe your symptoms and I'll guide you."
        )
        return

    if text == "About BisaRx":
        await send_text_message(
            sender,
            "ℹ️ *About BisaRx*\n\n"
            "BisaRx is a clinical care assistant that helps you get pharmacy guidance "
            "from the comfort of your home.\n\n"
            "• Describe your symptoms in a conversation\n"
            "• Our AI assistant gathers key details\n"
            "• A licensed pharmacist reviews your case\n"
            "• You receive professional guidance on treatment\n\n"
            "🔒 Your information is kept confidential.\n"
            "🌍 We support English and Twi."
        )
        return

    # Periodic cleanup
    _cleanup_stale_conversations()

    # Get or create conversation
    conversation = _get_conversation(sender)
    conversation.append({"role": "user", "content": text})

    # Process through the chat engine
    db = SessionLocal()
    try:
        result = chat_engine.process_chat(
            messages=conversation,
            db=db,
            user_id=None,  # WhatsApp users are guests
        )

        reply = result["reply"]
        is_consulting = result["consulting"]
        case_id = result.get("case_id")

        # Append assistant reply to conversation history
        conversation.append({"role": "assistant", "content": reply})

        if is_consulting and case_id:
            # Case was created and sent to pharmacist → send with buttons
            await send_text_message(sender, reply)
            await send_interactive_buttons(
                to=sender,
                body=f"📋 Your case #{case_id} has been submitted for pharmacist review.",
                buttons=[
                    {"id": f"btn_status_{case_id}", "title": "Check Status"},
                    {"id": "btn_new", "title": "New Conversation"},
                ],
            )
            # Reset conversation after case submission
            _conversations.pop(sender, None)
        else:
            # Regular reply – just send text
            await send_text_message(sender, reply)

    except Exception as exc:
        print(f"[WA] Error processing message from {sender}: {exc}")
        await send_text_message(
            sender,
            "I'm sorry, I encountered an issue processing your message. "
            "Please try again in a moment. 🙏"
        )
    finally:
        db.close()


# Handle "Check Status" button presses
async def _handle_status_check(sender: str, case_id: int):
    """Look up a case status and send it back."""
    db = SessionLocal()
    try:
        import models
        case = db.query(models.PrescriptionHistory).filter(
            models.PrescriptionHistory.id == case_id
        ).first()
        if not case:
            await send_text_message(sender, f"❌ Case #{case_id} not found.")
            return

        status_emoji = {
            "Pending": "⏳",
            "In Review": "🔍",
            "Reviewed": "✅",
            "Ordered": "📦",
            "Delivered": "🚚",
        }
        emoji = status_emoji.get(case.status, "📋")

        status_msg = (
            f"{emoji} *Case #{case.id} Status*\n\n"
            f"*Status:* {case.status}\n"
        )
        if case.pharmacist_feedback:
            status_msg += f"*Pharmacist feedback:* {case.pharmacist_feedback}\n"
        if case.drug_name and case.drug_name != "Pharmacist review required":
            status_msg += f"*Recommended treatment:* {case.drug_name}\n"
        if case.referral_advice:
            status_msg += f"*Referral:* {case.referral_advice}\n"
        if case.follow_up_instructions:
            status_msg += f"*Follow-up:* {case.follow_up_instructions}\n"

        if case.status == "Pending":
            status_msg += "\n_Your case is waiting for a pharmacist to review it. Please be patient._"
        elif case.status == "In Review":
            status_msg += "\n_A pharmacist is currently reviewing your case._"

        await send_text_message(sender, status_msg)
    finally:
        db.close()
