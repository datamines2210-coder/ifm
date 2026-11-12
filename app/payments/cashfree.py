"""Cashfree Hosted Web Checkout gateway.

Provider-specific HTTP/signature logic lives here; checkout orchestration stays in
app/main.py. This boundary is intentionally DB-agnostic for the planned MySQL move.
"""
import base64, hashlib, hmac, json, logging, threading, time, urllib.request
from typing import Dict, Optional
from ..config import settings

log=logging.getLogger('app.payments.cashfree')

class CashfreeGateway:
    def __init__(self):
        self._health_lock=threading.Lock(); self._health_status=None; self._health_checked_at=0

    def is_configured(self):
        return bool(settings.cashfree_app_id and settings.cashfree_secret_key)

    @property
    def environment(self):
        return 'production' if settings.cashfree_environment.lower()=='production' else 'sandbox'

    @property
    def base_url(self):
        return (settings.cashfree_production_base_url if self.environment=='production' else settings.cashfree_sandbox_base_url).rstrip('/')

    def _headers(self):
        return {'x-client-id':settings.cashfree_app_id,'x-client-secret':settings.cashfree_secret_key,
                'x-api-version':settings.cashfree_api_version,'Accept':'application/json','Content-Type':'application/json'}

    def _request(self, method, path, body=None, timeout=12):
        data=json.dumps(body).encode() if body is not None else None
        req=urllib.request.Request(self.base_url+path,data=data,method=method,headers=self._headers())
        with urllib.request.urlopen(req,timeout=timeout) as response:
            raw=response.read(); return json.loads(raw) if raw else {}

    def create_order(self, *, order_id:str, amount_paise:int, customer_id:str, customer_phone:str,
                     customer_email:str='', return_url:str='', notify_url:str='')->Dict:
        if not self.is_configured():
            return {'provider':'cashfree_unavailable','reason':'not_configured','id':order_id,'amount':amount_paise,'currency':'INR'}
        body={'order_id':order_id,'order_amount':round(amount_paise/100,2),'order_currency':'INR',
              'customer_details':{'customer_id':customer_id[:50], 'customer_phone':customer_phone}}
        if customer_email: body['customer_details']['customer_email']=customer_email
        meta={}
        if return_url: meta['return_url']=return_url
        if notify_url: meta['notify_url']=notify_url
        if meta: body['order_meta']=meta
        try:
            r=self._request('POST','/orders',body)
            return {'provider':'cashfree','id':r.get('order_id',order_id),'payment_session_id':r.get('payment_session_id',''),
                    'amount':amount_paise,'currency':'INR','environment':self.environment,'gateway_response':r}
        except Exception:
            log.exception('cashfree_create_order_failed order=%s',order_id)
            return {'provider':'cashfree_unavailable','reason':'create_order_failed','id':order_id,'amount':amount_paise,'currency':'INR'}

    def get_payments(self, order_id:str)->Optional[list]:
        if not self.is_configured(): return None
        try: return self._request('GET',f'/orders/{order_id}/payments')
        except Exception:
            log.exception('cashfree_get_payments_failed order=%s',order_id); return None

    def authoritative_status(self, order_id:str):
        payments=self.get_payments(order_id)
        if payments is None: return {'status':'unknown','payments':[]}
        statuses=[str(x.get('payment_status','')).upper() for x in payments if isinstance(x,dict)]
        if 'SUCCESS' in statuses: status='paid'
        elif 'PENDING' in statuses: status='pending'
        elif statuses: status='failed'
        else: status='pending'
        return {'status':status,'payments':payments}

    def verify_webhook_signature(self, raw_body:bytes, timestamp:str, signature:str)->bool:
        if not self.is_configured() or not timestamp or not signature: return False
        signed=timestamp.encode()+raw_body
        expected=base64.b64encode(hmac.new(settings.cashfree_secret_key.encode(),signed,hashlib.sha256).digest()).decode()
        return hmac.compare_digest(expected,signature)

    def health_check(self, force=False):
        with self._health_lock:
            now=time.time()
            if not force and self._health_status and now-self._health_checked_at<settings.cashfree_health_cache_seconds:
                status=self._health_status; cached=True
            elif not self.is_configured(): status='not_configured'; cached=False
            else:
                # Credentials are present. Avoid creating/fetching a financial resource solely for health.
                status='online'; cached=False
            self._health_status=status; self._health_checked_at=now
            msg={'online':'Cashfree is configured and ready.','not_configured':'Cashfree is not configured; Razorpay will be used as fallback.',
                 'offline':'Cashfree is temporarily unavailable; Razorpay will be used as fallback.'}.get(status,'Cashfree status is unknown.')
            return {'gateway':'cashfree','status':status,'configured':self.is_configured(),'environment':self.environment,
                    'checked_at':int(now),'cached':cached,'message':msg}
