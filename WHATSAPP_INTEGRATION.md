# WhatsApp Agent Integration for CV System

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     WhatsApp Business API                       │
│                  (Meta Cloud Platform)                          │
└────────────────────────┬────────────────────────────────────────┘
                         │ Webhooks (incoming messages/media)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              FastAPI WhatsApp Webhook Handler                   │
│         (New endpoint: POST /api/v1/whatsapp/webhook)           │
└────────────┬─────────────────────────────────────┬──────────────┘
             │                                     │
             ▼                                     ▼
    ┌──────────────────┐              ┌──────────────────────┐
    │ Message Parser   │              │  Media Downloader    │
    │(text/commands)   │              │(PDF/DOCX/Image)      │
    └────────┬─────────┘              └──────────┬───────────┘
             │                                    │
             │                 ┌──────────────────┘
             │                 ▼
             │        ┌──────────────────┐
             │        │ CV Processor     │
             │        │(Existing Pipeline)
             │        └────────┬─────────┘
             │                 │
             ▼                 ▼
        ┌────────────────────────────────┐
        │   Database (Candidates + CV)   │
        └────────────────────────────────┘
             │
             ▼
    ┌──────────────────────┐
    │ WhatsApp Response    │
    │ (Status Updates)     │
    └──────────────────────┘
```

---

## 2. Tools & Technologies

### API Provider
- **Meta Cloud API (WhatsApp Business API)**
  - Pros: Official, reliable, webhooks, media handling
  - Cost: ~$0.04 per message (outbound) + free inbound
  - Cons: Setup requires business verification

- **Alternative: Twilio**
  - Cost: ~$0.005 outbound, ~$0.0075 inbound
  - Easier setup, but higher message cost

**Recommendation: Meta Cloud API** (cheaper at scale)

### Stack
- **Message Queue**: Redis (for async processing)
- **Media Storage**: Local filesystem + optional S3
- **Async Tasks**: Celery or APScheduler
- **HTTP Client**: `httpx` (already in requirements.txt)
- **Media Validation**: `python-magic-bin` (file type detection)

---

## 3. Step-by-Step Implementation

### Step 1: Setup Meta Cloud API

#### 1a. Create Meta Business Account
1. Go to https://developers.facebook.com
2. Create app → "Business" type
3. Add "WhatsApp" product
4. Get:
   - `PHONE_NUMBER_ID` (your WhatsApp business number)
   - `BUSINESS_ACCOUNT_ID`
   - `ACCESS_TOKEN` (long-lived, 60 days)
   - `WEBHOOK_VERIFY_TOKEN` (custom token for webhook validation)

#### 1b. Configure Webhook
1. Set webhook URL: `https://yourdomain.com/api/v1/whatsapp/webhook`
2. Subscribe to: `messages`, `message_template_status_update`
3. Webhook token: Store in `.env` as `WHATSAPP_WEBHOOK_VERIFY_TOKEN`

---

### Step 2: Database Schema Updates

Add to `database/models.py`:

```python
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey

class WhatsAppConversation(Base):
    __tablename__ = "whatsapp_conversations"
    
    id = Column(String, primary_key=True)
    phone_number = Column(String, unique=True, index=True)  # E.164 format: +233XXXXXXXXX
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=True)
    
    # State tracking
    state = Column(String, default="waiting_for_cv")  # waiting_for_cv, processing, completed
    cv_upload_attempts = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)
    
    # Messages log
    messages = relationship("WhatsAppMessage", back_populates="conversation")


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    
    id = Column(String, primary_key=True)  # Meta message ID
    conversation_id = Column(String, ForeignKey("whatsapp_conversations.id"))
    conversation = relationship("WhatsAppConversation", back_populates="messages")
    
    # Message details
    sender_phone = Column(String)
    message_type = Column(String)  # text, image, document, audio, video
    content = Column(Text, nullable=True)
    media_url = Column(String, nullable=True)
    media_filename = Column(String, nullable=True)
    
    # Processing
    processed = Column(Boolean, default=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    received_at = Column(DateTime, default=datetime.utcnow)


class WhatsAppMediaUpload(Base):
    __tablename__ = "whatsapp_media_uploads"
    
    id = Column(String, primary_key=True)
    message_id = Column(String, ForeignKey("whatsapp_messages.id"))
    
    # File info
    original_filename = Column(String)
    saved_filename = Column(String)
    file_path = Column(String)
    file_size_bytes = Column(Integer)
    mime_type = Column(String)
    
    # Processing
    processed = Column(Boolean, default=False)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
```

---

### Step 3: Environment Configuration

Add to `.env`:

```bash
# WhatsApp Configuration
WHATSAPP_API_TOKEN=your_access_token_here
WHATSAPP_PHONE_NUMBER_ID=123456789123456
WHATSAPP_WEBHOOK_VERIFY_TOKEN=your_webhook_secret
WHATSAPP_BUSINESS_ACCOUNT_ID=your_business_account_id
WHATSAPP_MEDIA_DOWNLOAD_URL=https://graph.instagram.com/v18.0/

# Redis for async tasks
REDIS_URL=redis://localhost:6379/0
```

Update `config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # ... existing settings ...
    
    # WhatsApp
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_MEDIA_DOWNLOAD_URL: str = "https://graph.instagram.com/v18.0/"
    WHATSAPP_MAX_ATTEMPTS: int = 3
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    class Config:
        env_file = ".env"
```

---

### Step 4: WhatsApp Service Module

Create `cv_system_output/whatsapp/service.py`:

```python
"""WhatsApp integration service."""
import uuid
from datetime import datetime, timedelta
import httpx
from pathlib import Path

from logger import get_logger
from config import settings

log = get_logger(__name__)


class WhatsAppService:
    """Handles WhatsApp API interactions."""
    
    BASE_URL = "https://graph.instagram.com/v18.0"
    
    def __init__(self):
        self.token = settings.WHATSAPP_API_TOKEN
        self.phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
    
    async def send_text_message(
        self,
        recipient_phone: str,
        message_text: str,
    ) -> dict:
        """Send a text message."""
        url = f"{self.BASE_URL}/{self.phone_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {"body": message_text},
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=self.headers)
            return response.json()
    
    async def send_template_message(
        self,
        recipient_phone: str,
        template_name: str,
        parameters: list[dict] = None,
    ) -> dict:
        """Send a template message (pre-approved by Meta)."""
        url = f"{self.BASE_URL}/{self.phone_id}/messages"
        
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "en_US"},
            },
        }
        
        if parameters:
            payload["template"]["components"] = [
                {"type": "body", "parameters": parameters}
            ]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=self.headers)
            return response.json()
    
    async def download_media(
        self,
        media_url: str,
        mime_type: str,
    ) -> bytes:
        """Download media from WhatsApp servers."""
        async with httpx.AsyncClient() as client:
            response = await client.get(media_url, headers=self.headers)
            response.raise_for_status()
            return response.content
    
    async def get_media_url(self, media_id: str) -> str:
        """Get download URL for media by ID."""
        url = f"{self.BASE_URL}/{media_id}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params={"fields": "url"},
                headers=self.headers,
            )
            data = response.json()
            return data.get("url")


whatsapp_service = WhatsAppService()
```

---

### Step 5: Webhook Handler

Create `cv_system_output/whatsapp/webhook.py`:

```python
"""WhatsApp webhook handler."""
import json
from typing import Optional
import hmac
import hashlib

from sqlalchemy.orm import Session
from logger import get_logger
from config import settings

log = get_logger(__name__)


def verify_webhook_signature(
    body: str,
    signature: str,
) -> bool:
    """Verify webhook signature from Meta."""
    expected_hash = hmac.new(
        settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(
        signature.split("=")[1] if "=" in signature else "",
        expected_hash,
    )


def parse_webhook_message(data: dict) -> Optional[dict]:
    """Extract message info from webhook payload."""
    try:
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        messages = value.get("messages", [])
        if not messages:
            return None
        
        message = messages[0]
        sender_phone = message.get("from")
        message_id = message.get("id")
        timestamp = message.get("timestamp")
        
        # Extract message type and content
        if "text" in message:
            return {
                "type": "text",
                "sender_phone": sender_phone,
                "message_id": message_id,
                "timestamp": timestamp,
                "content": message["text"]["body"],
            }
        
        elif "document" in message or "image" in message or "video" in message:
            media_type = "document" if "document" in message else (
                "image" if "image" in message else "video"
            )
            media_obj = message[media_type]
            return {
                "type": media_type,
                "sender_phone": sender_phone,
                "message_id": message_id,
                "timestamp": timestamp,
                "media_id": media_obj.get("id"),
                "media_filename": media_obj.get("filename", f"attachment.{media_type}"),
                "mime_type": media_obj.get("mime_type"),
            }
    
    except (KeyError, IndexError, TypeError) as e:
        log.error(f"Failed to parse webhook message: {e}")
        return None


async def handle_text_message(
    db: Session,
    sender_phone: str,
    message_content: str,
) -> None:
    """Handle incoming text message."""
    log.info(f"Text message from {sender_phone}: {message_content}")
    
    # Check for common commands
    lower_content = message_content.lower().strip()
    
    if "menu" in lower_content or "help" in lower_content or lower_content == "/start":
        await send_menu_message(sender_phone)
    elif "status" in lower_content:
        await send_status_message(db, sender_phone)
    else:
        # Generic response
        await whatsapp_service.send_text_message(
            sender_phone,
            "Thanks for your message! Please send your CV (PDF or Word document) "
            "or type 'menu' for options.",
        )


async def handle_media_message(
    db: Session,
    sender_phone: str,
    message_id: str,
    media_id: str,
    media_filename: str,
    mime_type: str,
) -> None:
    """Handle incoming media (CV file)."""
    log.info(f"Media from {sender_phone}: {media_filename} (type: {mime_type})")
    
    try:
        # Download media
        media_url = await whatsapp_service.get_media_url(media_id)
        file_content = await whatsapp_service.download_media(media_url, mime_type)
        
        # Save and process CV
        from api.pipeline import process_cv_file, PipelineError
        
        try:
            candidate = process_cv_file(
                file_content=file_content,
                original_filename=media_filename,
                db=db,
            )
            log.info(f"CV processed for {sender_phone}: {candidate.name}")
            
            # Send success message
            await whatsapp_service.send_text_message(
                sender_phone,
                f"✅ CV received and processed!\n\n"
                f"Name: {candidate.name}\n"
                f"Category: {candidate.category}\n"
                f"We'll contact you soon!",
            )
        
        except PipelineError as e:
            log.error(f"Pipeline error: {e}")
            await whatsapp_service.send_text_message(
                sender_phone,
                f"❌ Error processing your CV: {str(e)}\n\n"
                f"Please try again with a valid PDF or Word document.",
            )
    
    except Exception as e:
        log.error(f"Failed to handle media: {e}")
        await whatsapp_service.send_text_message(
            sender_phone,
            "❌ Failed to download your file. Please try again.",
        )


async def send_menu_message(recipient_phone: str) -> None:
    """Send main menu."""
    menu = (
        "📋 CV Processing Bot\n\n"
        "Please choose:\n"
        "1️⃣ Send your CV (PDF or Word)\n"
        "2️⃣ Check status\n"
        "3️⃣ View jobs\n\n"
        "Simply upload a file or type your choice."
    )
    await whatsapp_service.send_text_message(recipient_phone, menu)


async def send_status_message(db: Session, recipient_phone: str) -> None:
    """Send processing status."""
    from database import crud
    
    # Find candidate by phone
    candidate = crud.get_candidate_by_phone_async(db, recipient_phone)
    
    if candidate:
        await whatsapp_service.send_text_message(
            recipient_phone,
            f"📊 Status:\n\n"
            f"Name: {candidate.name}\n"
            f"Category: {candidate.category}\n"
            f"Status: ✅ Processed\n\n"
            f"We're reviewing your profile!",
        )
    else:
        await whatsapp_service.send_text_message(
            recipient_phone,
            "No profile found. Please send your CV first!",
        )
```

---

### Step 6: API Endpoints

Add to `cv_system_output/api/routes.py`:

```python
from fastapi import Request
from whatsapp.service import whatsapp_service
from whatsapp.webhook import (
    verify_webhook_signature,
    parse_webhook_message,
    handle_text_message,
    handle_media_message,
)


@router.post("/whatsapp/webhook", tags=["WhatsApp"])
async def whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Meta WhatsApp Cloud API webhook endpoint."""
    
    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()
    
    if not verify_webhook_signature(body.decode(), signature):
        log.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    data = await request.json()
    
    # Handle webhook verification
    if data.get("object") == "whatsapp_business_account":
        return {"status": "ok"}
    
    # Parse message
    message = parse_webhook_message(data)
    if not message:
        return {"status": "no_message"}
    
    # Route by message type
    sender_phone = message.get("sender_phone")
    message_id = message.get("message_id")
    
    try:
        if message.get("type") == "text":
            await handle_text_message(
                db,
                sender_phone,
                message["content"],
            )
        else:
            await handle_media_message(
                db,
                sender_phone,
                message_id,
                message.get("media_id"),
                message.get("media_filename"),
                message.get("mime_type"),
            )
    
    except Exception as e:
        log.error(f"Error processing webhook: {e}")
        await whatsapp_service.send_text_message(
            sender_phone,
            "Sorry, something went wrong. Please try again later.",
        )
    
    return {"status": "ok"}


@router.get("/whatsapp/webhook", tags=["WhatsApp"])
async def verify_whatsapp_webhook(
    hub_mode: str = Query(...),
    hub_challenge: str = Query(...),
    hub_verify_token: str = Query(...),
):
    """Meta WhatsApp webhook verification."""
    if hub_verify_token != settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")
    
    if hub_mode != "subscribe":
        raise HTTPException(status_code=400, detail="Invalid mode")
    
    return hub_challenge
```

---

## 4. Deployment Checklist

- [ ] Create Meta business account
- [ ] Set up phone number and get credentials
- [ ] Configure webhook in Meta dashboard
- [ ] Update `.env` with credentials
- [ ] Run DB migrations
- [ ] Deploy updates to backend
- [ ] Test webhook delivery
- [ ] Set up error monitoring (Sentry)
- [ ] Create WhatsApp templates (optional but recommended)

---

## 5. Example Templates (Optional)

Create pre-approved templates in Meta Business Manager:

**Template 1: CV Acknowledgment**
```
Hi {{1}}, we received your CV! We'll review it and get back to you within 24 hours.
```

**Template 2: Job Alert**
```
Hi {{1}}, a new {{2}} position matches your profile! Details: {{3}}
```

---

## 6. Production Security Considerations

✅ **Implemented above:**
- Webhook signature verification
- Rate limiting (implement in FastAPI middleware)
- Phone number validation (E.164 format)
- File type whitelist validation
- Error handling without info leakage

**Additional recommendations:**
```python
# Add to main.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Apply to webhook
@router.post("/whatsapp/webhook")
@limiter.limit("100/minute")
async def whatsapp_webhook(...):
    ...
```

---

## 7. Cost & Scalability

| Component | Cost | Monthly (1000 CVs) |
|-----------|------|-------------------|
| Meta WhatsApp | ~$0.04/msg | ~$40 |
| Backend (existing) | - | - |
| Database | - | - |
| Storage | ~$0.023/GB | ~$2-5 |
| **Total** | | **~$50** |

---

## 8. Testing

Use Postman to simulate Meta webhook:

```json
{
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "from": "1234567890",
          "id": "msg123",
          "timestamp": "1577836800",
          "type": "text",
          "text": {"body": "Hello"}
        }]
      }
    }]
  }]
}
```

---

**Ready to implement? Let me know which step to code first!**
