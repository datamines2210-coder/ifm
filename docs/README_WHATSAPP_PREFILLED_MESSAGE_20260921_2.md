# WhatsApp pre-filled greeting — 2026-09-21

The Market floating WhatsApp button now opens the configured WhatsApp number with a pre-filled greeting:

`Hi! I have a question about your services.`

Configuration:
- `WHATSAPP_NUMBER` defaults to `+91 80507 60258`.
- `WHATSAPP_MESSAGE` defaults to the greeting above and can be overridden in `.env`.
- The server URL-encodes the message before returning the public WhatsApp URL.
- If `WHATSAPP_MESSAGE` is blank, the button opens the chat without a pre-filled message.
