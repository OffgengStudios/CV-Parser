# WhatsApp Integration - Remaining Steps

## STEP 9: Test Locally

### 9.1 Start the Backend

```powershell
cd "c:\Users\OFFGENG\Downloads\cv_system (1)\cv_system_output"
python main.py
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 9.2 Test Webhook Verification (GET)

Open your browser or use Postman:

```
GET http://localhost:8000/api/v1/whatsapp/webhook?hub.mode=subscribe&hub.challenge=test123&hub.verify_token=my_super_secret_webhook_token_123
```

Expected response:
```
200 OK
test123
```

### 9.3 Test Webhook Reception (POST)

Use Postman to simulate Meta sending a message:

**URL:**
```
POST http://localhost:8000/api/v1/whatsapp/webhook
```

**Headers:**
```
Content-Type: application/json
```

**Body (text message):**
```json
{
  "object": "whatsapp_business_account",
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "from": "1234567890",
          "id": "msg_test_123",
          "timestamp": "1234567890",
          "type": "text",
          "text": {"body": "Hello! This is a test message"}
        }]
      }
    }]
  }]
}
```

Expected response:
```json
{"status": "ok"}
```

Check backend logs for:
```
Text message from 1234567890: Hello! This is a test message
```

---

## STEP 10: Deploy to Production

### 10.1 Get Your Domain

You need a public domain/server with HTTPS (required by Meta).

Options:
- AWS, Azure, DigitalOcean, Heroku, Railway
- ngrok (for testing): `ngrok http 8000`

Example: `https://mycvapp.com/api/v1`

### 10.2 Configure Webhook in Meta Dashboard

1. Go to https://developers.facebook.com
2. Select your app → WhatsApp product
3. Configuration → Webhooks
4. Set webhook URL: `https://yourdom ain.com/api/v1/whatsapp/webhook`
5. Set webhook token: `my_super_secret_webhook_token_123` (same as `.env`)
6. Subscribe to: `messages`

### 10.3 Test on Real WhatsApp

1. Get test phone numbers:
   - Go to app → WhatsApp → Sandbox
   - You get a test number like `+1 555-555-0123`

2. Scan QR code with WhatsApp to join sandbox

3. Send your test number a message:
   - "Send /start"
   - You'll see bot response in WhatsApp

### 10.4 Deploy Code

Using Docker (recommended):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Deploy to:
- Docker Hub + Railway
- AWS ECS
- DigitalOcean App Platform

---

## TROUBLESHOOTING

### Issue: "WhatsApp not configured"

**Solution:** Check `.env` has:
```bash
WHATSAPP_API_TOKEN=EAA...
WHATSAPP_PHONE_NUMBER_ID=123...
```

### Issue: Webhook not receiving messages

**Solution:** 
1. Check webhook URL is public and HTTPS
2. Verify token matches Meta dashboard
3. Check logs: `tail -f cv_system.log`

### Issue: CV not processing from WhatsApp

**Solution:**
1. Check file is PDF/DOCX
2. File size < 10MB
3. Check backend logs for pipeline errors

### Issue: Media download fails

**Solution:**
1. Verify `WHATSAPP_API_TOKEN` is valid and not expired
2. Check file permissions in `uploads/` directory

---

## NEXT PHASE (Optional Enhancements)

- [ ] Job alert matching
- [ ] Candidate resume links
- [ ] Two-way messaging
- [ ] Payment integration
- [ ] Admin dashboard

