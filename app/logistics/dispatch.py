"""Delivery / logistics dispatch — storefront-only, independent of Travel/Sports.

Hybrid last-mile model (best-in-class hub-and-spoke pattern used by most Indian D2C brands):
  1. Primary: nearest regional fulfilment hub/dark-store books the shipment with a
     third-party logistics (3PL) courier partner (e.g. a Delhivery/Shiprocket-style
     aggregator) for standard multi-city delivery.
  2. Backup / last option: if no 3PL partner is configured or the booking fails,
     Indian Family dispatches the courier directly from Head Office / the nearest
     godown (self-fulfilled), guaranteeing every paid order still gets dispatched.

This mirrors the payment gateway's primary+fallback design (Cashfree primary + Razorpay fallback)
so operational risk (a courier partner outage) never blocks fulfilment.
"""
import time
import uuid
from typing import Dict, Optional

from ..config import settings
from ..db import upsert_delivery, get_delivery, update_delivery_status

# Regional hubs, cheapest-first by pincode prefix. Extend this list as new
# godowns/dark-stores open — no code elsewhere needs to change.
GODOWNS = [
    {"name": "Bengaluru Regional Hub", "city": "Bengaluru", "prefixes": ("56",)},
    {"name": "Delhi NCR Regional Hub", "city": "Delhi NCR", "prefixes": ("11",)},
    {"name": "Mumbai Regional Hub", "city": "Mumbai", "prefixes": ("40",)},
    {"name": "Chennai Regional Hub", "city": "Chennai", "prefixes": ("60",)},
    {"name": "Kolkata Regional Hub", "city": "Kolkata", "prefixes": ("70",)},
    {"name": "Hyderabad Regional Hub", "city": "Hyderabad", "prefixes": ("50",)},
]
HEAD_OFFICE_GODOWN = "Head Office Dispatch Godown"


def _pick_hub(pincode: str) -> str:
    for godown in GODOWNS:
        if pincode[:2] in godown["prefixes"]:
            return godown["name"]
    return HEAD_OFFICE_GODOWN


class RegionalCourierPartner:
    """Third-party logistics (3PL) aggregator — the primary dispatch channel."""

    def is_configured(self) -> bool:
        return bool(settings.courier_partner_api_key)

    def book_shipment(self, order_id: str, hub_name: str, pincode: str) -> Optional[str]:
        if not self.is_configured():
            return None
        # Real integration would call the 3PL's booking API here with settings.courier_partner_api_key.
        return f"3pl_{uuid.uuid4().hex[:12]}"


class DirectOfficeCourierService:
    """Backup / last option: Indian Family ships directly from office/godown."""

    def book_shipment(self, order_id: str) -> str:
        return f"ifm_courier_{uuid.uuid4().hex[:12]}"


class DispatchService:
    def __init__(self):
        self.partner = RegionalCourierPartner()
        self.office = DirectOfficeCourierService()

    def assign(self, order_id: str, pincode: str) -> Dict:
        pincode = (pincode or "").strip()
        hub_name = _pick_hub(pincode) if pincode else HEAD_OFFICE_GODOWN
        now = int(time.time())
        tracking_number = self.partner.book_shipment(order_id, hub_name, pincode)
        if tracking_number:
            dispatch_source, courier_partner, status = "regional_hub", "regional_3pl_partner", "assigned"
        else:
            tracking_number = self.office.book_shipment(order_id)
            hub_name = HEAD_OFFICE_GODOWN
            dispatch_source, courier_partner, status = "office_direct", "indian_family_courier", "assigned"
        eta_at = now + 3 * 86400 if dispatch_source == "regional_hub" else now + 5 * 86400
        upsert_delivery(order_id, dispatch_source, hub_name, courier_partner, tracking_number, status, eta_at, now)
        return {"order_id": order_id, "dispatch_source": dispatch_source, "hub_name": hub_name,
                "courier_partner": courier_partner, "tracking_number": tracking_number,
                "status": status, "eta_at": eta_at}

    def update_status(self, order_id: str, status: str, tracking_number: Optional[str] = None) -> bool:
        return update_delivery_status(order_id, status, tracking_number)

    def get_status(self, order_id: str):
        return get_delivery(order_id)


DELIVERY_STATUSES = ("pending", "assigned", "packed", "dispatched", "in_transit",
                     "out_for_delivery", "delivered", "delivery_failed", "returned")
