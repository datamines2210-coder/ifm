"""Read-only bounded Phase 7C internal SEO audit."""
from html.parser import HTMLParser
from urllib.parse import urlparse
from datetime import datetime,timezone
import json

class Tags(HTMLParser):
 def __init__(self):
  super().__init__();self.title='';self._title=False;self.desc=[];self.canon=[];self.robots=[];self.links=[];self.jsonld=[];self._json=False;self._part=''
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='title':self._title=True
  if t=='meta' and a.get('name','').lower()=='description':self.desc.append(a.get('content',''))
  if t=='meta' and a.get('name','').lower()=='robots':self.robots.append(a.get('content',''))
  if t=='link' and a.get('rel','').lower()=='canonical':self.canon.append(a.get('href',''))
  if t=='a' and a.get('href'):self.links.append(a['href'])
  if t=='script' and a.get('type','').lower()=='application/ld+json':self._json=True;self._part=''
 def handle_data(self,d):
  if self._title:self.title+=d
  if self._json:self._part+=d
 def handle_endtag(self,t):
  if t=='title':self._title=False
  if t=='script' and self._json:self.jsonld.append(self._part);self._json=False

def inspect_pages(pages,origin,sitemap_paths):
 findings=[];seen={};known={x[0] for x in pages};inventory=[]
 for path,status,html in pages[:30]:
  t=Tags();t.feed(html or '');title=t.title.strip();desc=t.desc[0].strip() if t.desc else '';robots=t.robots[0].lower() if t.robots else ''
  def issue(rule,severity,detail):findings.append(dict(path=path,rule=rule,severity=severity,detail=detail))
  if status!=200:issue('http_status','critical',f'HTTP {status}')
  if not title:issue('missing_title','high','No title')
  elif title in seen:issue('duplicate_title','medium','Same title as '+seen[title])
  else:seen[title]=path
  if not desc:issue('missing_description','medium','No meta description')
  if len(t.canon)!=1:issue('canonical_count','high','Expected one canonical')
  elif t.canon[0]!=origin.rstrip('/')+path:issue('canonical_mismatch','high','Canonical differs from configured origin and route')
  if 'noindex' in robots:issue('noindex','high','Noindex directive')
  if path not in sitemap_paths and 'noindex' not in robots:issue('missing_sitemap','medium','Not in sitemap')
  for raw in t.jsonld:
   try:json.loads(raw)
   except (ValueError,TypeError):issue('invalid_jsonld','medium','Invalid JSON-LD')
  for link in t.links:
   u=urlparse(link)
   if (not u.netloc or u.netloc==urlparse(origin).netloc) and u.path.startswith(('/products/','/category/')) and u.path not in known:issue('unresolved_internal_link','low','Not in bounded inventory: '+u.path)
  inventory.append(dict(path=path,status=status,title=title,canonical=t.canon[0] if t.canon else '',robots=robots))
 return dict(checked_at=datetime.now(timezone.utc).isoformat(),pages_checked=len(inventory),findings=findings[:150],summary={s:sum(x['severity']==s for x in findings) for s in ('critical','high','medium','low')},inventory=inventory,scope='read-only bounded internal route audit; no external crawl')
