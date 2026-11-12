import hashlib, hmac, json, logging, urllib.request
from typing import Dict
from .config import settings

log = logging.getLogger("app.services")

class PaymentService:
    def __init__(self):
        self.client = None
        if settings.razorpay_key_id and settings.razorpay_key_secret:
            try:
                import razorpay
                self.client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
            except ImportError:
                log.warning("razorpay_sdk_not_installed")

    def create_order(self, amount_paise: int, receipt: str) -> Dict:
        if self.client:
            order = self.client.order.create({"amount": amount_paise, "currency": "INR", "receipt": receipt})
            return {"provider": "razorpay", "id": order["id"], "amount": amount_paise, "currency": "INR", "receipt": receipt, "key_id": settings.razorpay_key_id}
        return {"provider": "mock", "id": f"mock_{receipt}", "amount": amount_paise, "currency": "INR", "receipt": receipt, "key_id": settings.razorpay_key_id}

    def verify_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        if self.client:
            try:
                self.client.utility.verify_payment_signature({
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": signature,
                })
                return True
            except Exception:
                return False
        if not settings.razorpay_key_secret:
            return False
        message = f"{order_id}|{payment_id}".encode()
        expected = hmac.new(settings.razorpay_key_secret.encode(), message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

class AlertService:
    def send(self, event: str, payload: dict):
        if not settings.alert_webhook_url:
            log.warning("alert_not_configured event=%s payload=%s", event, payload)
            return False
        data = json.dumps({"event": event, "payload": payload}).encode()
        req = urllib.request.Request(settings.alert_webhook_url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                return 200 <= response.status < 300
        except Exception:
            log.exception("alert_delivery_failed event=%s", event)
            return False
