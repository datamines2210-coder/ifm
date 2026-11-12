"""Phase 5 read-only SEO measurement connectors; no storefront dependencies."""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from .db import connect

PROVIDERS = ('google', 'bing')


def configured(provider):
    if provider == 'google':
        return bool(os.getenv('SEO_GSC_PROPERTY') and os.getenv('SEO_GSC_SERVICE_ACCOUNT_FILE'))
    if provider == 'bing':
        return bool(os.getenv('SEO_BING_SITE_URL') and os.getenv('SEO_BING_API_KEY'))
    raise ValueError('Unknown SEO provider')


def _fetch_google():
    # Lazy optional dependency: absent credentials never affect Market startup.
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    credentials = service_account.Credentials.from_service_account_file(
        os.environ['SEO_GSC_SERVICE_ACCOUNT_FILE'],
        scopes=['https://www.googleapis.com/auth/webmasters.readonly'])
    credentials.refresh(Request())
    property_url = os.environ['SEO_GSC_PROPERTY']
    end = date.today() - timedelta(days=3)  # GSC data can be delayed
    start = end - timedelta(days=27)
    url = 'https://searchconsole.googleapis.com/webmasters/v3/sites/' + urllib.parse.quote(property_url, safe='') + '/searchAnalytics/query'
    def fetch_dimension(dim, row_limit):
        body = json.dumps({'startDate': start.isoformat(), 'endDate': end.isoformat(),
                           'dimensions': [dim], 'rowLimit': row_limit}).encode()
        request = urllib.request.Request(url, data=body, headers={
            'Authorization': 'Bearer ' + credentials.token, 'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response).get('rows', [])
    daily_rows = fetch_dimension('date', 100)
    # Query and page results are sampled top rows from Search Console, not a complete export.
    query_rows = fetch_dimension('query', 250)
    page_rows = fetch_dimension('page', 250)
    def normalize(rows, label):
        return [{label: str(r.get('keys', [''])[0]), 'clicks': r.get('clicks', 0),
                 'impressions': r.get('impressions', 0), 'ctr': r.get('ctr', 0),
                 'position': r.get('position', 0)} for r in rows]
    return {'period_start': start.isoformat(), 'period_end': end.isoformat(),
            'clicks': sum(float(r.get('clicks', 0)) for r in daily_rows),
            'impressions': sum(float(r.get('impressions', 0)) for r in daily_rows),
            'daily': normalize(daily_rows, 'date'), 'queries': normalize(query_rows, 'query'),
            'pages': normalize(page_rows, 'page'), 'dimensions_source': 'google_search_console',
            'dimensions_limit': 250}


def _fetch_bing():
    site = os.environ['SEO_BING_SITE_URL']
    key = os.environ['SEO_BING_API_KEY']
    # JSON REST API. Key remains exclusively server-side.
    params = urllib.parse.urlencode({'siteUrl': site, 'apikey': key})
    url = 'https://ssl.bing.com/webmaster/api.svc/json/GetRankAndTrafficStats?' + params
    request = urllib.request.Request(url, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    # Preserve provider-specific data; avoid inventing common KPI semantics.
    return {'site': site, 'provider_data': payload.get('d', payload)}


def status():
    with connect() as c:
        rows = {r['provider']: dict(r) for r in c.execute('SELECT provider,status,updated_at,last_success_at,error_message FROM seo_integration_status')}
    return [{'provider': p, 'configured': configured(p), 'state': rows.get(p, {}).get('status', 'never_run'),
             'updated_at': rows.get(p, {}).get('updated_at'),
             'last_success_at': rows.get(p, {}).get('last_success_at'),
             'error': rows.get(p, {}).get('error_message', '')} for p in PROVIDERS]


def snapshots(provider, limit=30):
    if provider not in PROVIDERS: raise ValueError('Unknown SEO provider')
    with connect() as c:
        rows = c.execute('SELECT id,provider,captured_at,metrics_json FROM seo_measurement_snapshots WHERE provider=? ORDER BY captured_at DESC LIMIT ?', (provider, max(1, min(int(limit), 90)))).fetchall()
    return [{'id': r['id'], 'provider': r['provider'], 'captured_at': r['captured_at'],
             'metrics': json.loads(r['metrics_json'])} for r in rows]


def refresh(provider, actor):
    if provider not in PROVIDERS: raise ValueError('Unknown SEO provider')
    if not configured(provider): raise ValueError('Provider not configured')
    now = int(time.time())
    # Limit refresh to 1 per 15 minutes, including failed attempts.
    with connect() as c:
        last = c.execute('SELECT updated_at FROM seo_integration_status WHERE provider=?', (provider,)).fetchone()
        if last and now - last['updated_at'] < 900: raise ValueError('Refresh cooldown: retry after 15 minutes')
        c.execute('INSERT INTO seo_integration_status(provider,status,updated_at) VALUES(?,?,?) ON CONFLICT(provider) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at,error_message=\'\'', (provider, 'running', now))
    try:
        metrics = _fetch_google() if provider == 'google' else _fetch_bing()
        with connect() as c:
            c.execute('INSERT INTO seo_measurement_snapshots(provider,captured_at,metrics_json) VALUES(?,?,?)', (provider, int(time.time()), json.dumps(metrics)))
            c.execute('UPDATE seo_integration_status SET status=?,updated_at=?,last_success_at=?,error_message=? WHERE provider=?', ('success', int(time.time()), int(time.time()), '', provider))
            c.execute('INSERT INTO seo_integration_audit(provider,actor_id,action,occurred_at) VALUES(?,?,?,?)', (provider, actor, 'refresh_success', int(time.time())))
        return {'status': 'success', 'provider': provider}
    except Exception as exc:
        # Never expose upstream URLs (Bing API key in query string) or tokens.
        with connect() as c:
            c.execute('UPDATE seo_integration_status SET status=?,updated_at=?,error_message=? WHERE provider=?', ('failed', int(time.time()), type(exc).__name__, provider))
            c.execute('INSERT INTO seo_integration_audit(provider,actor_id,action,occurred_at) VALUES(?,?,?,?)', (provider, actor, 'refresh_failed', int(time.time())))
        return {'status': 'failed', 'provider': provider, 'error': 'Provider request failed; inspect secure server logs'}
