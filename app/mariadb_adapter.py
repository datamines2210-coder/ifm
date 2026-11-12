"""Opt-in MariaDB compatibility connection. No schema creation or implicit migration."""
import re
import os
from urllib.parse import urlsplit, unquote

REQUIRED_TABLES = frozenset(('users','orders','catalog','auth_logs','auth_sessions','payment_transactions','customer_profiles','catalog_category_media','admin_credentials','payment_settings','seo_documents','seo_revisions'))

class HybridRow(dict):
    """Support SQLite-style row['column'], row[0], and dict(row)."""
    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = tuple(values)
    def __getitem__(self, key):
        return self._values[key] if isinstance(key, int) else super().__getitem__(key)

class CursorAdapter:
    def __init__(self, cursor): self._cursor = cursor
    @property
    def rowcount(self): return self._cursor.rowcount
    @property
    def lastrowid(self): return self._cursor.lastrowid
    def fetchone(self):
        row = self._cursor.fetchone()
        return HybridRow([c[0] for c in self._cursor.description], row) if row is not None else None
    def fetchall(self):
        return [HybridRow([c[0] for c in self._cursor.description], row) for row in self._cursor.fetchall()]
    def __iter__(self):
        for row in self._cursor:
            yield HybridRow([c[0] for c in self._cursor.description], row)

# Explicit dialect translation only for patterns identified in the supplied source.
def translate_sql(sql):
    original = sql
    if re.match(r'^\s*BEGIN IMMEDIATE\s*$', sql, re.I):
        return 'START TRANSACTION'
    if re.search(r'\b(?:PRAGMA|AUTOINCREMENT|sqlite_master|executescript)\b', sql, re.I):
        raise ValueError('SQLite-only SQL is not permitted in MariaDB mode')
    sql = re.sub(r'\bCOLLATE\s+NOCASE\b', 'COLLATE utf8mb4_unicode_ci', sql, flags=re.I)
    sql = re.sub(r'^\s*INSERT\s+OR\s+IGNORE\s+INTO\b', 'INSERT IGNORE INTO', sql, flags=re.I)
    conflict = re.search(r'\bON\s+CONFLICT\s*\(\s*(?:`[A-Za-z_][A-Za-z_0-9]*`|[A-Za-z_][A-Za-z_0-9]*)\s*\)\s+DO\s+UPDATE\s+SET\s+', sql, flags=re.I)
    if conflict:
        prefix, updates = sql[:conflict.start()], sql[conflict.end():]
        updates = re.sub(r'\bexcluded\.([A-Za-z_][A-Za-z_0-9]*)\b', lambda m: 'VALUES('+m.group(1)+')', updates, flags=re.I)
        sql = prefix + ' ON DUPLICATE KEY UPDATE ' + updates
    elif re.search(r'\bON\s+CONFLICT\b', sql, re.I):
        raise ValueError('Unsupported SQLite conflict syntax')
    # Only placeholders outside quoted strings and comments are rewritten.
    out=[]; i=0; quote=None
    while i < len(sql):
        ch=sql[i]
        if quote:
            out.append(ch)
            if ch=='\\' and i+1<len(sql): i+=1; out.append(sql[i])
            elif ch==quote:
                if i+1<len(sql) and sql[i+1]==quote: i+=1; out.append(sql[i])
                else: quote=None
        elif ch in ("'", '"', '`'): quote=ch; out.append(ch)
        elif ch=='-' and sql[i:i+2]=='--':
            end=sql.find('\n',i); end=len(sql) if end<0 else end
            out.append(sql[i:end]); i=end-1
        elif ch=='?': out.append('%s')
        elif ch=='%': out.append('%%')
        else: out.append(ch)
        i+=1
    return ''.join(out)

class MariaConnection:
    def __init__(self, raw): self.raw=raw
    def commit(self):
        return self.raw.commit()
    def rollback(self):
        return self.raw.rollback()
    def close(self):
        try:
            self.raw.rollback()
        finally:
            self.raw.close()
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type: self.raw.rollback()
            else: self.raw.commit()
        finally: self.raw.close()
    def execute(self, sql, params=()):
        cursor=self.raw.cursor()
        try: cursor.execute(translate_sql(sql), tuple(params))
        except BaseException: cursor.close(); raise
        return CursorAdapter(cursor)
    def executemany(self, sql, values):
        cursor=self.raw.cursor()
        try: cursor.executemany(translate_sql(sql), values)
        except BaseException: cursor.close(); raise
        return CursorAdapter(cursor)
    def executescript(self, *_): raise RuntimeError('MariaDB schema creation is disabled')

def connect_mariadb(url):
    try: import pymysql
    except ImportError as exc: raise RuntimeError('PyMySQL is required for MariaDB mode') from exc
    parts=urlsplit(url)
    if parts.scheme not in ('mysql+pymysql', 'mariadb+pymysql') or not parts.hostname or not parts.path.strip('/'):
        raise ValueError('Invalid database URL configuration. Check DATABASE_URL settings.')
    if parts.hostname != '127.0.0.1' or (parts.port or 3306) != 3306:
        raise RuntimeError('Production MariaDB host/port not allowed')
    if unquote(parts.path.lstrip('/')) != 'ifm_market_v2':
        raise RuntimeError('Production MariaDB database not allowed')
    if unquote(parts.username or '') != 'ifm_market_v2_app':
        raise RuntimeError('Production MariaDB username not allowed')
    raw=pymysql.connect(host=parts.hostname, port=parts.port or 3306,
        user=unquote(parts.username or ''), password=unquote(parts.password or ''),
        database=unquote(parts.path.lstrip('/')), charset='utf8mb4', autocommit=False,
        connect_timeout=5, read_timeout=10, write_timeout=10)
    return MariaConnection(raw)

def verify_schema(conn):
    rows=conn.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE=?', ('BASE TABLE',)).fetchall()
    found={r[0] for r in rows}
    missing=REQUIRED_TABLES-found
    if missing: raise RuntimeError('MariaDB schema missing required tables: '+', '.join(sorted(missing)))
    return True
