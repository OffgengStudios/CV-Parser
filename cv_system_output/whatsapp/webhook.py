"""WhatsApp webhook handler - processes incoming messages from Meta Cloud API."""
import json
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from logger import get_logger
from whatsapp.service import whatsapp_service
from database import crud

log = get_logger(__name__)


def parse_webhook_message(data: dict) -> Optional[dict]:
    """
    Extract message info from Meta webhook payload.

    Meta sends: {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{...}]
                }
            }]
        }]
    }

    Returns:
        Dict with: type, sender_phone, message_id, timestamp, content/media_id
    """
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

        elif "document" in message:
            media_obj = message["document"]
            return {
                "type": "document",
                "sender_phone": sender_phone,
                "message_id": message_id,
                "timestamp": timestamp,
                "media_id": media_obj.get("id"),
                "media_filename": media_obj.get("filename", "document.pdf"),
                "mime_type": media_obj.get("mime_type", "application/pdf"),
            }

        elif "image" in message:
            media_obj = message["image"]
            return {
                "type": "image",
                "sender_phone": sender_phone,
                "message_id": message_id,
                "timestamp": timestamp,
                "media_id": media_obj.get("id"),
                "media_filename": media_obj.get("filename", "image.jpg"),
                "mime_type": media_obj.get("mime_type", "image/jpeg"),
            }

        elif "video" in message:
            media_obj = message["video"]
            return {
                "type": "video",
                "sender_phone": sender_phone,
                "message_id": message_id,
                "timestamp": timestamp,
                "media_id": media_obj.get("id"),
                "media_filename": media_obj.get("filename", "video.mp4"),
                "mime_type": media_obj.get("mime_type", "video/mp4"),
            }

    except (KeyError, IndexError, TypeError) as e:
        log.error(f"Failed to parse webhook message: {e}")
        return None

    return None


async def handle_text_message(
    db: Session,
    sender_phone: str,
    message_content: str,
) -> None:
    """
    Handle incoming text message.

    Commands:
    - 'menu', 'help', '/start': Show menu
    - 'status': Check candidate status
    """
    log.info(f"Text message from {sender_phone}: {message_content}")

    # Normalize input
    lower_content = message_content.lower().strip()

    if any(keyword in lower_content for keyword in ["menu", "help", "start", "options"]):
        await send_menu_message(sender_phone)
    elif "status" in lower_content:
        await send_status_message(db, sender_phone)
    else:
        # Generic response
        await whatsapp_service.send_text_message(
            sender_phone,
            "Thanks for your message! 📩\n\n"
            "To get started, please send your CV (PDF or Word document).\n"
            "Type 'menu' for more options.",
        )


async def handle_media_message(
    db: Session,
    sender_phone: str,
    message_id: str,
    media_id: str,
    media_filename: str,
    mime_type: str,
) -> None:
    """
    Handle incoming media (CV file).

    Flow:
    1. Get media download URL
    2. Download file
    3. Process with existing CV pipeline
    4. Store in database
    5. Send confirmation to user
    """
    log.info(f"Media from {sender_phone}: {media_filename} (type: {mime_type})")

    try:
        # Step 1: Get or create conversation
        conversation = crud.get_or_create_whatsapp_conversation(db, sender_phone)

        # Step 2: Create message record
        whatsapp_message = crud.create_whatsapp_message(
            db=db,
            message_id=message_id,
            conversation_id=conversation.id,
            sender_phone=sender_phone,
            message_type="document" if "pdf" in mime_type or "word" in mime_type else "media",
            media_filename=media_filename,
        )

        # Step 3: Get download URL
        media_url = await whatsapp_service.get_media_url(media_id)
        if not media_url:
            log.error(f"Could not get media URL for {media_id}")
            await whatsapp_service.send_text_message(
                sender_phone,
                "❌ Failed to download your file. Please try again.",
            )
            return

        # Step 4: Download file
        file_content = await whatsapp_service.download_media(media_url)
        if not file_content:
            log.error(f"Failed to download media from {media_url}")
            await whatsapp_service.send_text_message(
                sender_phone,
                "❌ Failed to download your file. Please try again.",
            )
            return

        # Step 5: Process CV using existing pipeline
        from api.pipeline import process_cv_file, PipelineError

        try:
            candidate = process_cv_file(
                file_content=file_content,
                original_filename=media_filename,
                db=db,
            )
            log.info(f"CV processed for {sender_phone}: {candidate.name} (ID: {candidate.id})")

            # Step 6: Link conversation to candidate
            crud.update_whatsapp_conversation(
                db=db,
                conversation_id=conversation.id,
                candidate_id=candidate.id,
                state="completed",
            )

            # Step 7: Update media upload record
            crud.create_whatsapp_media_upload(
                db=db,
                message_id=message_id,
                original_filename=media_filename,
                saved_filename=candidate.saved_upload_filename or media_filename,
                file_path=f"uploads/{candidate.saved_upload_filename}",
                file_size_bytes=len(file_content),
                mime_type=mime_type,
            )

            # Step 8: Send success message
            await whatsapp_service.send_text_message(
                sender_phone,
                f"✅ *CV Received and Processed!*\n\n"
                f"*Name:* {candidate.name or 'Not found'}\n"
                f"*Category:* {candidate.category or 'Unknown'}\n"
                f"*Skills:* {len(candidate.skills) or 0}\n\n"
                f"We'll review your profile shortly! 🎯"
            )

        except PipelineError as e:
            log.error(f"Pipeline error processing CV: {e}")

            # Update conversation state
            crud.update_whatsapp_conversation(
                db=db,
                conversation_id=conversation.id,
                state="failed",
            )

            await whatsapp_service.send_text_message(
                sender_phone,
                f"❌ *Error Processing CV*\n\n"
                f"Details: {str(e)}\n\n"
                f"Please try again with a valid PDF or Word document."
            )

    except Exception as e:
        log.error(f"Unexpected error handling media: {e}", exc_info=True)
        await whatsapp_service.send_text_message(
            sender_phone,
            "❌ An unexpected error occurred. Please try again later or contact support.",
        )


async def send_menu_message(recipient_phone: str) -> None:
    """Send main menu to user."""
    menu = (
        "📋 *CV Processing Bot - Main Menu*\n\n"
        "What would you like to do?\n\n"
        "1️⃣  *Send CV* - Upload your CV (PDF or Word)\n"
        "2️⃣  *Check Status* - View your application status\n"
        "3️⃣  *Job Alerts* - Get matching job opportunities\n\n"
        "Simply upload a file or type a number! 📤"
    )
    await whatsapp_service.send_text_message(recipient_phone, menu)


async def send_status_message(db: Session, recipient_phone: str) -> None:
    """Send candidate status message."""
    # Find candidate by phone
    candidate = crud.get_candidate_by_phone(db, recipient_phone)

    if candidate:
        status_msg = (
            f"📊 *Your Application Status*\n\n"
            f"*Name:* {candidate.name or 'Not found'}\n"
            f"*Category:* {candidate.category or 'Unknown'}\n"
            f"*Experience:* {candidate.years_experience or '?'} years\n"
            f"*Skills Matched:* {len(candidate.skills) or 0}\n"
            f"*Status:* ✅ Under Review\n\n"
            f"We'll notify you when there's a match! 🎯"
        )
    else:
        status_msg = (
            "❓ *No Profile Found*\n\n"
            "We don't have your CV yet. "
            "Please send your CV (PDF or Word document) to get started! 📄"
        )

    await whatsapp_service.send_text_message(recipient_phone, status_msg)


async def send_onboarding_message(recipient_phone: str) -> None:
    """Send welcome/onboarding message."""
    welcome = (
        "👋 *Welcome to Our CV Processing System!*\n\n"
        "I'm an automated bot that helps process your CV and find matching job opportunities.\n\n"
        "🚀 *Getting Started:*\n"
        "Send your CV (PDF or Word document) and I'll:\n"
        "✓ Extract your information\n"
        "✓ Classify your skills\n"
        "✓ Match you with jobs\n\n"
        "Ready? Send your CV now! 📤"
    )
    await whatsapp_service.send_text_message(recipient_phone, welcome)
