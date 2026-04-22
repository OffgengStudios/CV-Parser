"""WhatsApp integration service - handles API communication with Meta Cloud API."""
import httpx
from typing import Optional

from logger import get_logger
from config import settings

log = get_logger(__name__)


class WhatsAppService:
    """Handles WhatsApp Business API interactions with Meta Cloud."""

    BASE_URL = "https://graph.instagram.com/v18.0"

    def __init__(self):
        self.token = settings.WHATSAPP_API_TOKEN
        self.phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        if not self.token or not self.phone_id:
            log.warning(
                "WhatsApp credentials not configured. "
                "Set WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID in .env"
            )

    async def send_text_message(
        self,
        recipient_phone: str,
        message_text: str,
    ) -> dict:
        """
        Send a text message via WhatsApp Business API.

        Args:
            recipient_phone: Phone number in E.164 format (+233XXXXXXXXX)
            message_text: Message body (max 4096 characters)

        Returns:
            API response dict with message_id on success
        """
        if not self.token or not self.phone_id:
            log.error("WhatsApp not configured")
            return {"error": "WhatsApp not configured"}

        url = f"{self.BASE_URL}/{self.phone_id}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_phone,
            "type": "text",
            "text": {"body": message_text},
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                result = response.json()
                log.info(f"Message sent to {recipient_phone}: {result.get('messages', [{}])[0].get('id', 'unknown')}")
                return result
        except httpx.HTTPError as e:
            log.error(f"Failed to send message to {recipient_phone}: {e}")
            return {"error": str(e)}

    async def send_template_message(
        self,
        recipient_phone: str,
        template_name: str,
        language_code: str = "en_US",
        parameters: Optional[list[dict]] = None,
    ) -> dict:
        """
        Send a pre-approved template message.

        Args:
            recipient_phone: Phone number in E.164 format
            template_name: Name of approved template (e.g., 'cv_received')
            language_code: Language code (default: en_US)
            parameters: List of parameter dicts for template substitution

        Returns:
            API response dict
        """
        if not self.token or not self.phone_id:
            log.error("WhatsApp not configured")
            return {"error": "WhatsApp not configured"}

        url = f"{self.BASE_URL}/{self.phone_id}/messages"

        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }

        if parameters:
            payload["template"]["components"] = [
                {"type": "body", "parameters": parameters}
            ]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=self.headers)
                response.raise_for_status()
                result = response.json()
                log.info(f"Template message sent to {recipient_phone}")
                return result
        except httpx.HTTPError as e:
            log.error(f"Failed to send template to {recipient_phone}: {e}")
            return {"error": str(e)}

    async def download_media(
        self,
        media_url: str,
    ) -> Optional[bytes]:
        """
        Download media file from WhatsApp servers.

        Args:
            media_url: Download URL from Media Object

        Returns:
            File bytes or None on error
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(media_url, headers=self.headers)
                response.raise_for_status()
                log.info(f"Downloaded media ({len(response.content)} bytes)")
                return response.content
        except httpx.HTTPError as e:
            log.error(f"Failed to download media: {e}")
            return None

    async def get_media_url(self, media_id: str) -> Optional[str]:
        """
        Get download URL for media by ID.

        Args:
            media_id: Media object ID from incoming message

        Returns:
            Download URL or None on error
        """
        if not self.token:
            log.error("WhatsApp not configured")
            return None

        url = f"{self.BASE_URL}/{media_id}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    url,
                    params={"fields": "url"},
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()
                media_url = data.get("url")
                if media_url:
                    log.info(f"Got media URL for {media_id}")
                    return media_url
                else:
                    log.warning(f"No URL in media response: {data}")
                    return None
        except httpx.HTTPError as e:
            log.error(f"Failed to get media URL: {e}")
            return None


# Singleton instance
whatsapp_service = WhatsAppService()
