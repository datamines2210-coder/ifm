"""Deprecated compatibility module.

AU Bank is not a direct payment provider for Indian Family Market. Cashfree is the
primary gateway and Razorpay is the backup. This stub intentionally contains no AU
credentials, endpoints, or transaction implementation and may be removed after all
deployments have received the Cashfree migration hot patch.
"""

class AUBankGateway:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("AU Bank direct gateway is retired; use CashfreeGateway")
