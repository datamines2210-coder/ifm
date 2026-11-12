import sqlite3
import re
import uuid
from urllib.parse import unquote
from .models import PRODUCTS, Product
from .auth import hash_password
from pathlib import Path
from .config import settings
from .mariadb_adapter import connect_mariadb, verify_schema


def db_path():
    value = settings.database_url
    if value.startswith('sqlite:///'):
        return Path(value[10:]).resolve()
    raise RuntimeError('This starter currently supports SQLite DATABASE_URL only')


def is_mariadb():
    return settings.database_url.startswith(('mysql+pymysql://', 'mariadb+pymysql://'))


def connect():
    if is_mariadb():
        return connect_mariadb(settings.database_url)
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if is_mariadb():
        with connect() as c:
            verify_schema(c)
        return
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE,
            phone TEXT,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',
            must_change_password INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS customer_profiles (
            user_id TEXT PRIMARY KEY, address_line1 TEXT NOT NULL DEFAULT '', address_line2 TEXT NOT NULL DEFAULT '',
            city TEXT NOT NULL DEFAULT '', state TEXT NOT NULL DEFAULT '', pincode TEXT NOT NULL DEFAULT '',
            locality TEXT NOT NULL DEFAULT '', latitude REAL, longitude REAL,
            bank_name TEXT NOT NULL DEFAULT '', bank_account_masked TEXT NOT NULL DEFAULT '', ifsc TEXT NOT NULL DEFAULT '',
            updated_at INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS auth_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'customer',
            created_at INTEGER NOT NULL,
            last_activity_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            logged_out_at INTEGER DEFAULT NULL,
            ip_address TEXT DEFAULT '',
            user_agent TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_activity ON auth_sessions(last_activity_at);
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            razorpay_order_id TEXT,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            status TEXT NOT NULL,
            items_json TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            customer_name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            pincode TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            delivery_date TEXT NOT NULL DEFAULT '',
            delivery_slot TEXT NOT NULL DEFAULT '',
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE TABLE IF NOT EXISTS payments (
            razorpay_payment_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            signature TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS catalog (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
            state TEXT NOT NULL, price REAL NOT NULL, mrp REAL NOT NULL,
            unit TEXT NOT NULL, description TEXT NOT NULL, image TEXT,
            parent_url TEXT, active INTEGER NOT NULL DEFAULT 1, status TEXT NOT NULL DEFAULT 'live',
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS offers (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, slogan TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '',
            offer_type TEXT NOT NULL DEFAULT 'informational', value REAL NOT NULL DEFAULT 0, code TEXT NOT NULL DEFAULT '',
            scope TEXT NOT NULL DEFAULT 'site', target TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '',
            cta_text TEXT NOT NULL DEFAULT '', cta_link TEXT NOT NULL DEFAULT '', placement TEXT NOT NULL DEFAULT 'offers',
            status TEXT NOT NULL DEFAULT 'draft', priority INTEGER NOT NULL DEFAULT 100, start_at INTEGER, end_at INTEGER,
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_offers_status_dates ON offers(status,start_at,end_at,priority);
        CREATE TABLE IF NOT EXISTS payment_settings (
            id INTEGER PRIMARY KEY CHECK (id=1), provider TEXT NOT NULL DEFAULT 'cashfree',
            razorpay_checkout_url TEXT NOT NULL DEFAULT 'https://pages.razorpay.com/tifa',
            upi_id TEXT NOT NULL DEFAULT '', upi_name TEXT NOT NULL DEFAULT '',
            upi_redirect_url TEXT NOT NULL DEFAULT '', updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS site_content (
            key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '',
            link TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1, updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS admin_credentials (
            id INTEGER PRIMARY KEY CHECK (id=1), password_hash TEXT NOT NULL, updated_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY, user_id TEXT, order_id TEXT DEFAULT '',
            subject TEXT NOT NULL, message TEXT NOT NULL DEFAULT '', rating INTEGER DEFAULT NULL,
            status TEXT NOT NULL DEFAULT 'new', created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status);
        CREATE TABLE IF NOT EXISTS deliveries (
            order_id TEXT PRIMARY KEY,
            dispatch_source TEXT NOT NULL DEFAULT 'unassigned',
            hub_name TEXT NOT NULL DEFAULT '',
            courier_partner TEXT NOT NULL DEFAULT '',
            tracking_number TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            eta_at INTEGER DEFAULT NULL,
            created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        );
        CREATE INDEX IF NOT EXISTS idx_deliveries_status ON deliveries(status);
        CREATE TABLE IF NOT EXISTS auth_logs (
            id TEXT PRIMARY KEY, occurred_at INTEGER NOT NULL, event_type TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 1, user_id TEXT DEFAULT '', identity TEXT DEFAULT '',
            ip_address TEXT DEFAULT '', user_agent TEXT DEFAULT '', details TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_auth_logs_occurred ON auth_logs(occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_auth_logs_user ON auth_logs(user_id);
        CREATE TABLE IF NOT EXISTS auth_logs_archive (
            id TEXT PRIMARY KEY, occurred_at INTEGER NOT NULL, event_type TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 1, user_id TEXT DEFAULT '', identity TEXT DEFAULT '',
            ip_address TEXT DEFAULT '', user_agent TEXT DEFAULT '', details TEXT DEFAULT '',
            archived_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_auth_logs_archive_occurred ON auth_logs_archive(occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_auth_logs_archive_user ON auth_logs_archive(user_id);
        CREATE TABLE IF NOT EXISTS login_otps (
            id TEXT PRIMARY KEY, identity TEXT NOT NULL, user_id TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL,
            code_hash TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, used_at INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_login_otps_identity ON login_otps(identity, created_at DESC);
        ''')
        # SEO Phase 2: additive revision/publishing store. It is intentionally Market-only.
        c.executescript('''
        CREATE TABLE IF NOT EXISTS seo_documents (
            id TEXT PRIMARY KEY,
            resource_type TEXT NOT NULL,
            resource_key TEXT NOT NULL,
            published_revision_id TEXT DEFAULT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            UNIQUE(resource_type, resource_key)
        );
        CREATE INDEX IF NOT EXISTS idx_seo_documents_resource ON seo_documents(resource_type, resource_key);
        CREATE TABLE IF NOT EXISTS seo_revisions (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            revision_no INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            title TEXT NOT NULL DEFAULT '',
            meta_description TEXT NOT NULL DEFAULT '',
            canonical_url TEXT NOT NULL DEFAULT '',
            robots TEXT NOT NULL DEFAULT 'index,follow',
            og_title TEXT NOT NULL DEFAULT '',
            og_description TEXT NOT NULL DEFAULT '',
            og_image TEXT NOT NULL DEFAULT '',
            structured_data_json TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL,
            reviewed_by TEXT NOT NULL DEFAULT '',
            published_by TEXT NOT NULL DEFAULT '',
            created_at INTEGER NOT NULL,
            reviewed_at INTEGER DEFAULT NULL,
            published_at INTEGER DEFAULT NULL,
            UNIQUE(document_id, revision_no),
            FOREIGN KEY(document_id) REFERENCES seo_documents(id)
        );
        CREATE INDEX IF NOT EXISTS idx_seo_revisions_document ON seo_revisions(document_id, revision_no DESC);
        CREATE INDEX IF NOT EXISTS idx_seo_revisions_status ON seo_revisions(status, created_at DESC);
        CREATE TABLE IF NOT EXISTS seo_audit_events (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL DEFAULT '',
            revision_id TEXT NOT NULL DEFAULT '',
            actor_id TEXT NOT NULL DEFAULT '',
            actor_role TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            occurred_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_seo_audit_occurred ON seo_audit_events(occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_seo_audit_document ON seo_audit_events(document_id, occurred_at DESC);
        ''')

        # Phase 5: additive read-only measurement snapshots and safe diagnostics.
        c.executescript('''
        CREATE TABLE IF NOT EXISTS seo_measurement_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL,
            captured_at INTEGER NOT NULL, metrics_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_seo_measurement_provider_time ON seo_measurement_snapshots(provider,captured_at DESC);
        CREATE TABLE IF NOT EXISTS seo_integration_status (
            provider TEXT PRIMARY KEY, status TEXT NOT NULL,
            updated_at INTEGER NOT NULL, last_success_at INTEGER,
            error_message TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS seo_integration_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL,
            actor_id TEXT NOT NULL, action TEXT NOT NULL, occurred_at INTEGER NOT NULL
        );
        ''')

        catalog_columns = {row[1] for row in c.execute('PRAGMA table_info(catalog)').fetchall()}
        if 'status' not in catalog_columns:
            c.execute("ALTER TABLE catalog ADD COLUMN status TEXT NOT NULL DEFAULT 'live'")
        columns = {row[1] for row in c.execute('PRAGMA table_info(users)').fetchall()}
        if 'role' not in columns:
            c.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'customer'")
        if 'username' not in columns:
            c.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if 'must_change_password' not in columns:
            c.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
        # Backfill usernames for legacy customer accounts created before username login existed.
        # Prefer a readable slug from the display name and make it unique deterministically.
        legacy_users = c.execute("SELECT id,name,email FROM users WHERE username IS NULL OR trim(username)='' ORDER BY created_at,id").fetchall()
        used = {str(r[0]).lower() for r in c.execute("SELECT username FROM users WHERE username IS NOT NULL AND trim(username)<>''").fetchall()}
        for legacy in legacy_users:
            base = re.sub(r'[^a-z0-9]+', '', (legacy['name'] or '').strip().lower())[:40]
            if not base:
                base = re.sub(r'[^a-z0-9]+', '', (legacy['email'] or '').split('@', 1)[0].lower())[:40] or 'user'
            candidate = base
            suffix = 2
            while candidate in used or candidate in {settings.admin_username.lower(), settings.admin_email.lower()}:
                candidate = f"{base}{suffix}"
                suffix += 1
            c.execute("UPDATE users SET username=? WHERE id=?", (candidate, legacy['id']))
            used.add(candidate)

        feedback_columns = {row[1] for row in c.execute('PRAGMA table_info(feedback)').fetchall()}
        if 'admin_response' not in feedback_columns:
            c.execute("ALTER TABLE feedback ADD COLUMN admin_response TEXT NOT NULL DEFAULT ''")

        profile_columns = {row[1] for row in c.execute('PRAGMA table_info(customer_profiles)').fetchall()}
        for col, ddl in [("locality", "ALTER TABLE customer_profiles ADD COLUMN locality TEXT NOT NULL DEFAULT ''"),
                         ("latitude", "ALTER TABLE customer_profiles ADD COLUMN latitude REAL"),
                         ("longitude", "ALTER TABLE customer_profiles ADD COLUMN longitude REAL")]:
            if col not in profile_columns:
                c.execute(ddl)
        c.execute('''CREATE TABLE IF NOT EXISTS catalog_category_media (
            category TEXT PRIMARY KEY, image TEXT NOT NULL DEFAULT '', updated_at INTEGER NOT NULL DEFAULT 0
        )''')
        category_columns = {row[1] for row in c.execute('PRAGMA table_info(catalog_category_media)').fetchall()}
        for col, ddl in [("display_name", "ALTER TABLE catalog_category_media ADD COLUMN display_name TEXT NOT NULL DEFAULT ''"),("description", "ALTER TABLE catalog_category_media ADD COLUMN description TEXT NOT NULL DEFAULT ''"),("active", "ALTER TABLE catalog_category_media ADD COLUMN active INTEGER NOT NULL DEFAULT 1"),("sort_order", "ALTER TABLE catalog_category_media ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 100"),("category_id", "ALTER TABLE catalog_category_media ADD COLUMN category_id TEXT NOT NULL DEFAULT ''")]:
            if col not in category_columns: c.execute(ddl)
        for row in c.execute("SELECT category FROM catalog_category_media WHERE category_id='' OR category_id IS NULL").fetchall():
            c.execute("UPDATE catalog_category_media SET category_id=? WHERE category=?", (uuid.uuid4().hex,row[0]))
        for row in c.execute("SELECT DISTINCT category FROM catalog WHERE trim(category)<>''").fetchall():
            if not c.execute("SELECT 1 FROM catalog_category_media WHERE category=?",(row[0],)).fetchone():
                c.execute("INSERT INTO catalog_category_media(category,image,updated_at,display_name,description,active,sort_order,category_id) VALUES(?,?,?,?,?,?,?,?)",(row[0],'',0,row[0],'',1,100,uuid.uuid4().hex))
        order_columns = {row[1] for row in c.execute('PRAGMA table_info(orders)').fetchall()}
        for col, ddl in [("customer_name", "ALTER TABLE orders ADD COLUMN customer_name TEXT NOT NULL DEFAULT ''"),
                         ("phone", "ALTER TABLE orders ADD COLUMN phone TEXT NOT NULL DEFAULT ''"),
                         ("pincode", "ALTER TABLE orders ADD COLUMN pincode TEXT NOT NULL DEFAULT ''"),
                         ("address", "ALTER TABLE orders ADD COLUMN address TEXT NOT NULL DEFAULT ''"),
                         ("delivery_date", "ALTER TABLE orders ADD COLUMN delivery_date TEXT NOT NULL DEFAULT ''"),
                         ("delivery_slot", "ALTER TABLE orders ADD COLUMN delivery_slot TEXT NOT NULL DEFAULT ''")]:
            if col not in order_columns:
                c.execute(ddl)
        # One-time administrator credential migration requested for production.
        admin_columns = {x[1] for x in c.execute("PRAGMA table_info(admin_credentials)").fetchall()}
        if "credential_version" not in admin_columns:
            c.execute("ALTER TABLE admin_credentials ADD COLUMN credential_version INTEGER NOT NULL DEFAULT 1")
        for col, ddl in [("name", "ALTER TABLE admin_credentials ADD COLUMN name TEXT NOT NULL DEFAULT 'Administrator'"),
                         ("email", "ALTER TABLE admin_credentials ADD COLUMN email TEXT NOT NULL DEFAULT ''"),
                         ("username", "ALTER TABLE admin_credentials ADD COLUMN username TEXT NOT NULL DEFAULT ''"),
                         ("phone", "ALTER TABLE admin_credentials ADD COLUMN phone TEXT NOT NULL DEFAULT ''")]:
            if col not in admin_columns:
                c.execute(ddl)
        c.execute("UPDATE admin_credentials SET name=COALESCE(NULLIF(name,''),'Administrator'), email=COALESCE(NULLIF(email,''),?), username=COALESCE(NULLIF(username,''),?), phone=COALESCE(NULLIF(phone,''),?) WHERE id=1",
                  (settings.admin_email, settings.admin_username, settings.admin_phone))
        c.execute("UPDATE admin_credentials SET password_hash=?, credential_version=2, updated_at=? WHERE id=1 AND COALESCE(credential_version, 1)<2",
                  (hash_password(settings.admin_password), int(__import__('time').time())))
        now = int(__import__('time').time())
        c.execute("INSERT OR IGNORE INTO payment_settings(id, updated_at, razorpay_checkout_url) VALUES(1, ?, ?)", (now, 'https://pages.razorpay.com/tifa'))
        # Migrate known legacy Market Razorpay hosted-page defaults to the current payment page.
        # Custom administrator-configured URLs are intentionally preserved.
        c.execute("UPDATE payment_settings SET razorpay_checkout_url=?, updated_at=? WHERE razorpay_checkout_url IN (?, ?, '')",
                  ('https://pages.razorpay.com/tifa', now, 'https://rzp.io/rzp/tifm', 'https://pages.razorpay.com/tifm'))
        # AU Bank is no longer a direct provider; Cashfree is the primary payment gateway.
        c.execute("UPDATE payment_settings SET provider='cashfree', updated_at=? WHERE provider='au_bank'", (now,))
        c.execute("""CREATE TABLE IF NOT EXISTS payment_transactions (
            id TEXT PRIMARY KEY, order_id TEXT NOT NULL, provider TEXT NOT NULL, provider_order_id TEXT NOT NULL DEFAULT '',
            provider_payment_id TEXT NOT NULL DEFAULT '', payment_session_id TEXT NOT NULL DEFAULT '',
            amount_paise INTEGER NOT NULL, currency TEXT NOT NULL DEFAULT 'INR', status TEXT NOT NULL DEFAULT 'created',
            environment TEXT NOT NULL DEFAULT '', idempotency_key TEXT NOT NULL DEFAULT '', is_test INTEGER NOT NULL DEFAULT 0,
            gateway_status TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, verified_at INTEGER,
            FOREIGN KEY(order_id) REFERENCES orders(id)
        )""")
        c.execute('CREATE INDEX IF NOT EXISTS idx_payment_tx_order ON payment_transactions(order_id, created_at DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_payment_tx_status ON payment_transactions(provider, status, updated_at)')
        c.execute("INSERT OR IGNORE INTO admin_credentials(id, password_hash, updated_at, credential_version) VALUES(1, ?, ?, 2)",
              (hash_password(settings.admin_password), now))
        c.execute("UPDATE admin_credentials SET name=COALESCE(NULLIF(name,''),'Administrator'), email=COALESCE(NULLIF(email,''),?), username=COALESCE(NULLIF(username,''),?), phone=COALESCE(NULLIF(phone,''),?) WHERE id=1",
                  (settings.admin_email, settings.admin_username, settings.admin_phone))
        if c.execute('SELECT COUNT(*) FROM catalog').fetchone()[0] == 0:
            now = int(__import__('time').time())
            c.executemany('INSERT INTO catalog(id,name,category,state,price,mrp,unit,description,image,parent_url,active,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)', [
                (p.id, p.name, p.category, p.state, p.price, p.mrp, p.unit,
                 p.description, p.image, p.parent_url, int(p.active), getattr(p,'status','live'), now, now)
                for p in PRODUCTS
            ])



def create_auth_session(session_id, user_id, email, role, created_at, expires_at, ip_address="", user_agent=""):
    # Market identity policy: exactly one active session per user across desktop/mobile.
    # A successful new login atomically closes every older session before creating the new one.
    with connect() as c:
        c.execute("UPDATE auth_sessions SET logged_out_at=? WHERE user_id=? AND logged_out_at IS NULL", (created_at, user_id))
        c.execute("INSERT INTO auth_sessions(session_id,user_id,email,role,created_at,last_activity_at,expires_at,ip_address,user_agent) VALUES(?,?,?,?,?,?,?,?,?)",
                  (session_id, user_id, email or "", role or "customer", created_at, created_at, expires_at, ip_address or "", user_agent or ""))


def touch_auth_session(session_id, now, ip_address="", user_agent=""):
    idle_limit = 4 * 60 * 60
    with connect() as c:
        row = c.execute("SELECT * FROM auth_sessions WHERE session_id=?", (session_id,)).fetchone()
        if not row or row["logged_out_at"] is not None or row["expires_at"] <= now:
            return False
        if now - int(row["last_activity_at"] or row["created_at"]) > idle_limit:
            c.execute("UPDATE auth_sessions SET logged_out_at=? WHERE session_id=?", (now, session_id))
            return False
        c.execute("UPDATE auth_sessions SET last_activity_at=?, ip_address=COALESCE(NULLIF(?, ''), ip_address), user_agent=COALESCE(NULLIF(?, ''), user_agent) WHERE session_id=?",
                  (now, ip_address or "", user_agent or "", session_id))
        return True


def revoke_auth_session(session_id, now):
    with connect() as c:
        c.execute("UPDATE auth_sessions SET logged_out_at=? WHERE session_id=? AND logged_out_at IS NULL", (now, session_id))


def get_customer_profile(user_id):
    with connect() as c:
        row=c.execute("SELECT * FROM customer_profiles WHERE user_id=?",(user_id,)).fetchone()
        if row: return row
        c.execute("INSERT INTO customer_profiles(user_id,updated_at) VALUES(?,?)",(user_id,int(__import__('time').time())))
        return c.execute("SELECT * FROM customer_profiles WHERE user_id=?",(user_id,)).fetchone()

def update_customer_profile(user_id, data, admin=False):
    current=dict(get_customer_profile(user_id))
    allowed={'address_line1','address_line2','city','state','pincode','locality','latitude','longitude'}
    if admin: allowed |= {'bank_name','bank_account_masked','ifsc'}
    current.update({k:v for k,v in data.items() if k in allowed})
    with connect() as c:
        c.execute("""UPDATE customer_profiles SET address_line1=?,address_line2=?,city=?,state=?,pincode=?,locality=?,latitude=?,longitude=?,bank_name=?,bank_account_masked=?,ifsc=?,updated_at=? WHERE user_id=?""",
          (current['address_line1'],current['address_line2'],current['city'],current['state'],current['pincode'],current.get('locality',''),current.get('latitude'),current.get('longitude'),current['bank_name'],current['bank_account_masked'],current['ifsc'],int(__import__('time').time()),user_id))
    return get_customer_profile(user_id)

def update_user_details(user_id, name, email, username, phone):
    with connect() as c:
        c.execute("UPDATE users SET name=?,email=?,username=?,phone=? WHERE id=?",(name,email.lower().strip(),username.lower().strip() or None,phone,user_id))

def list_auth_sessions(active_only=False):
    q="SELECT s.*, COALESCE(u.name, CASE WHEN s.user_id='admin' THEN 'Administrator' ELSE s.user_id END) AS name FROM auth_sessions s LEFT JOIN users u ON u.id=s.user_id"
    if active_only: q += ' WHERE s.logged_out_at IS NULL'
    q += ' ORDER BY s.last_activity_at DESC'
    with connect() as c: return c.execute(q).fetchall()

def admin_revoke_auth_session(session_id):
    revoke_auth_session(session_id, int(__import__('time').time()))

def list_catalog(include_inactive=False):
    with connect() as c:
        query = 'SELECT * FROM catalog'
        if not include_inactive:
            query += ' WHERE active=1'
        return c.execute(query + ' ORDER BY created_at DESC').fetchall()


def catalog_product(product_id):
    with connect() as c:
        return c.execute('SELECT * FROM catalog WHERE id=?', (product_id,)).fetchone()


def save_catalog_product(data, product_id=None):
    now = int(__import__('time').time())
    with connect() as c:
        if product_id:
            c.execute('''UPDATE catalog SET name=?,category=?,state=?,price=?,mrp=?,unit=?,
                description=?,image=?,parent_url=?,active=?,status=?,updated_at=? WHERE id=?''',
                (data['name'], data['category'], data['state'], data['price'], data['mrp'],
                 data['unit'], data['description'], data.get('image', ''), data.get('parent_url', ''),
                 int(data.get('active', True)), data.get('status','live'), now, product_id))
        else:
            c.execute('''INSERT INTO catalog(id,name,category,state,price,mrp,unit,description,image,parent_url,active,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (data['id'], data['name'], data['category'], data['state'], data['price'], data['mrp'],
                 data['unit'], data['description'], data.get('image', ''), data.get('parent_url', ''),
                 int(data.get('active', True)), data.get('status','live'), now, now))


def delete_catalog_product(product_id):
    with connect() as c:
        c.execute('UPDATE catalog SET active=0, updated_at=? WHERE id=?',
                  (int(__import__('time').time()), product_id))


def archive_catalog_products(product_ids):
    ids=[str(x).strip() for x in product_ids if str(x).strip()]
    if not ids: return 0
    marks=','.join('?' for _ in ids)
    with connect() as c:
        cur=c.execute(f'UPDATE catalog SET active=0, status=\'archived\', updated_at=? WHERE id IN ({marks})',
                      (int(__import__('time').time()), *ids))
        return cur.rowcount

def catalog_products_referenced_by_orders(product_ids):
    wanted={str(x).strip() for x in product_ids if str(x).strip()}
    found=set()
    if not wanted: return []
    with connect() as c:
        rows=c.execute('SELECT items_json FROM orders').fetchall()
    import json
    for row in rows:
        try: items=json.loads(row['items_json'] or '[]')
        except Exception: continue
        for item in items if isinstance(items,list) else []:
            pid=str(item.get('id') or item.get('product_id') or '').strip() if isinstance(item,dict) else ''
            if pid in wanted: found.add(pid)
    return sorted(found)

def hard_delete_catalog_products(product_ids):
    ids=[str(x).strip() for x in product_ids if str(x).strip()]
    if not ids: return 0
    marks=','.join('?' for _ in ids)
    with connect() as c:
        cur=c.execute(f'DELETE FROM catalog WHERE id IN ({marks})', ids)
        return cur.rowcount


def find_user_by_email(email):
    with connect() as c:
        return c.execute('SELECT * FROM users WHERE email=?', (email.lower().strip(),)).fetchone()


def find_user_by_login(login):
    with connect() as c:
        value = login.lower().strip()
        return c.execute('SELECT * FROM users WHERE lower(email)=? OR lower(username)=?', (value, value)).fetchone()


def find_user(user_id):
    with connect() as c:
        return c.execute('SELECT id,name,email,username,phone,role,must_change_password,created_at FROM users WHERE id=?', (user_id,)).fetchone()


def create_user(user_id, name, email, phone, password_hash, created_at, role='customer', username='', must_change_password=False):
    with connect() as c:
        c.execute('INSERT INTO users(id,name,email,username,phone,password_hash,role,must_change_password,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                  (user_id,name,email.lower().strip(),username.lower().strip() or None,phone,password_hash,role,int(must_change_password),created_at))


def list_users():
    with connect() as c:
        return c.execute('''SELECT u.id,u.name,u.email,u.username,u.phone,u.role,u.must_change_password,u.created_at,
            (SELECT MAX(s.last_activity_at) FROM auth_sessions s WHERE s.user_id=u.id) AS last_activity_at,
            (SELECT COUNT(*) FROM orders o WHERE o.user_id=u.id) AS order_count
            FROM users u ORDER BY u.created_at DESC''').fetchall()


def update_user_password(user_id, password_hash):
    with connect() as c:
        c.execute('UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?', (password_hash, user_id))


def update_user_role(user_id, role):
    with connect() as c:
        c.execute('UPDATE users SET role=? WHERE id=?', (role, user_id))
        # Existing signed tokens carry the old role. Close them so the new role takes effect immediately.
        c.execute('UPDATE auth_sessions SET logged_out_at=? WHERE user_id=? AND logged_out_at IS NULL', (int(__import__('time').time()), user_id))


def get_payment_settings():
    with connect() as c:
        return c.execute('SELECT * FROM payment_settings WHERE id=1').fetchone()


def save_payment_settings(data):
    with connect() as c:
        c.execute('''UPDATE payment_settings SET provider=?, razorpay_checkout_url=?, upi_id=?,
            upi_name=?, upi_redirect_url=?, updated_at=? WHERE id=1''',
            (data['provider'], data['razorpay_checkout_url'], data['upi_id'], data['upi_name'],
             data['upi_redirect_url'], int(__import__('time').time())))


def list_site_content(include_inactive=False):
    with connect() as c:
        query = 'SELECT * FROM site_content'
        if not include_inactive:
            query += ' WHERE active=1'
        return c.execute(query + ' ORDER BY `key`').fetchall()


def save_site_content(data):
    with connect() as c:
        c.execute('''INSERT INTO site_content(`key`,value,image,link,active,updated_at)
            VALUES(?,?,?,?,?,?) ON CONFLICT(`key`) DO UPDATE SET value=excluded.value,
            image=excluded.image,link=excluded.link,active=excluded.active,updated_at=excluded.updated_at''',
            (data['key'], data.get('value', ''), data.get('image', ''), data.get('link', ''),
             int(data.get('active', True)), int(__import__('time').time())))


def get_admin_profile():
    with connect() as c:
        row = c.execute("SELECT name,email,username,phone,updated_at FROM admin_credentials WHERE id=1").fetchone()
        if not row:
            return {"name":"Administrator","email":settings.admin_email,"username":settings.admin_username,"phone":settings.admin_phone,"updated_at":0}
        return dict(row)

def update_admin_profile(name, email, username, phone):
    with connect() as c:
        c.execute("UPDATE admin_credentials SET name=?,email=?,username=?,phone=?,updated_at=? WHERE id=1",
                  (name.strip(), email.lower().strip(), username.lower().strip(), phone.strip(), int(__import__('time').time())))
    return get_admin_profile()

def get_admin_password_hash():
    with connect() as c:
        row = c.execute('SELECT password_hash FROM admin_credentials WHERE id=1').fetchone()
        return row['password_hash'] if row else ''


def save_admin_password(password_hash):
    with connect() as c:
        c.execute('UPDATE admin_credentials SET password_hash=?, updated_at=? WHERE id=1',
                  (password_hash, int(__import__('time').time())))


def create_order(order_id, user_id, razorpay_order_id, amount, currency, status, items_json, created_at,
                  customer_name='', phone='', pincode='', address='', delivery_date='', delivery_slot=''):
    with connect() as c:
        c.execute('''INSERT INTO orders(id,user_id,razorpay_order_id,amount,currency,status,items_json,created_at,
            customer_name,phone,pincode,address,delivery_date,delivery_slot) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (order_id,user_id,razorpay_order_id,amount,currency,status,items_json,created_at,
             customer_name,phone,pincode,address,delivery_date,delivery_slot))


def get_order(order_id):
    with connect() as c:
        return c.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()


def get_order_by_gateway_reference(gateway_reference):
    # razorpay_order_id is reused generically to store whichever gateway's order/reference id
    # Legacy compatibility column. New provider-neutral references live in payment_transactions.
    with connect() as c:
        return c.execute('SELECT * FROM orders WHERE razorpay_order_id=?', (gateway_reference,)).fetchone()


def list_orders_for_user(user_id, limit=200):
    limit = max(1, min(int(limit), 2000))
    with connect() as c:
        return c.execute('SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?', (user_id, limit)).fetchall()


def list_orders(status=None, limit=500):
    limit = max(1, min(int(limit), 5000))
    with connect() as c:
        if status:
            return c.execute('SELECT * FROM orders WHERE status=? ORDER BY created_at DESC LIMIT ?', (status, limit)).fetchall()
        return c.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()


def set_order_status(order_id, status):
    with connect() as c:
        c.execute('UPDATE orders SET status=? WHERE id=?', (status, order_id))


def add_payment(payment_id, order_id, signature, status, created_at):
    with connect() as c:
        c.execute('INSERT INTO payments VALUES(?,?,?,?,?)', (payment_id,order_id,signature,status,created_at))


def get_payment_for_order(order_id):
    with connect() as c:
        return c.execute('SELECT * FROM payments WHERE order_id=? ORDER BY created_at DESC LIMIT 1', (order_id,)).fetchone()


def create_feedback(feedback_id, user_id, order_id, subject, message, rating, created_at):
    with connect() as c:
        c.execute('''INSERT INTO feedback(id,user_id,order_id,subject,message,rating,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,'new',?,?)''',
            (feedback_id, user_id, order_id or '', subject, message, rating, created_at, created_at))


def list_feedback_for_user(user_id, limit=200):
    limit = max(1, min(int(limit), 2000))
    with connect() as c:
        return c.execute('SELECT * FROM feedback WHERE user_id=? ORDER BY created_at DESC LIMIT ?', (user_id, limit)).fetchall()


def list_feedback(status=None, limit=500):
    limit = max(1, min(int(limit), 5000))
    with connect() as c:
        if status:
            return c.execute('SELECT * FROM feedback WHERE status=? ORDER BY created_at DESC LIMIT ?', (status, limit)).fetchall()
        return c.execute('SELECT * FROM feedback ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()


def update_feedback_status(feedback_id, status, admin_response=None):
    with connect() as c:
        if not c.execute('SELECT id FROM feedback WHERE id=?', (feedback_id,)).fetchone():
            return False
        if admin_response is None:
            c.execute('UPDATE feedback SET status=?, updated_at=? WHERE id=?', (status, int(__import__('time').time()), feedback_id))
        else:
            c.execute('UPDATE feedback SET status=?, admin_response=?, updated_at=? WHERE id=?', (status, admin_response, int(__import__('time').time()), feedback_id))
    return True


def upsert_delivery(order_id, dispatch_source, hub_name, courier_partner, tracking_number, status, eta_at, created_at):
    with connect() as c:
        c.execute('''INSERT INTO deliveries(order_id,dispatch_source,hub_name,courier_partner,tracking_number,status,eta_at,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET dispatch_source=excluded.dispatch_source,
            hub_name=excluded.hub_name, courier_partner=excluded.courier_partner, tracking_number=excluded.tracking_number,
            status=excluded.status, eta_at=excluded.eta_at, updated_at=excluded.updated_at''',
            (order_id, dispatch_source, hub_name, courier_partner, tracking_number, status, eta_at, created_at, created_at))


def get_delivery(order_id):
    with connect() as c:
        return c.execute('SELECT * FROM deliveries WHERE order_id=?', (order_id,)).fetchone()


def update_delivery_status(order_id, status, tracking_number=None):
    with connect() as c:
        if not c.execute('SELECT order_id FROM deliveries WHERE order_id=?', (order_id,)).fetchone():
            return False
        if tracking_number is not None:
            c.execute('UPDATE deliveries SET status=?, tracking_number=?, updated_at=? WHERE order_id=?',
                      (status, tracking_number, int(__import__('time').time()), order_id))
        else:
            c.execute('UPDATE deliveries SET status=?, updated_at=? WHERE order_id=?',
                      (status, int(__import__('time').time()), order_id))
    return True


def list_deliveries(status=None, limit=500):
    limit = max(1, min(int(limit), 5000))
    with connect() as c:
        if status:
            return c.execute('SELECT * FROM deliveries WHERE status=? ORDER BY created_at DESC LIMIT ?', (status, limit)).fetchall()
        return c.execute('SELECT * FROM deliveries ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()


def log_auth_event(log_id, occurred_at, event_type, success=True, user_id='', identity='', ip_address='', user_agent='', details=''):
    with connect() as c:
        c.execute('''INSERT INTO auth_logs(id,occurred_at,event_type,success,user_id,identity,ip_address,user_agent,details)
            VALUES(?,?,?,?,?,?,?,?,?)''',
            (log_id, occurred_at, event_type, int(bool(success)), user_id, identity, ip_address, user_agent, details))
    run_auth_log_retention_maintenance()


_AUTH_LOG_MAINTENANCE_LAST_RUN = 0


def run_auth_log_retention_maintenance(force=False):
    # Throttled to at most once/day: archives events older than auth_log_archive_after_days
    # (1 year) into auth_logs_archive, then purges archived events past
    # auth_log_purge_after_days (3 years total). See app/config.py.
    global _AUTH_LOG_MAINTENANCE_LAST_RUN
    now = int(__import__('time').time())
    if not force and now - _AUTH_LOG_MAINTENANCE_LAST_RUN < 86400:
        return None
    _AUTH_LOG_MAINTENANCE_LAST_RUN = now
    archived = archive_old_auth_logs(now - settings.auth_log_archive_after_days * 86400)
    purged = purge_old_archived_auth_logs(now - settings.auth_log_purge_after_days * 86400)
    return {"archived": archived, "purged": purged}


def list_auth_logs(user_id=None, start_at=None, end_at=None, limit=500):
    limit = max(1, min(int(limit), 5000))
    query = 'SELECT * FROM auth_logs WHERE 1=1'
    params = []
    if user_id:
        query += ' AND user_id=?'
        params.append(user_id)
    if start_at is not None:
        query += ' AND occurred_at>=?'
        params.append(start_at)
    if end_at is not None:
        query += ' AND occurred_at<?'
        params.append(end_at)
    query += ' ORDER BY occurred_at DESC LIMIT ?'
    params.append(limit)
    with connect() as c:
        return c.execute(query, params).fetchall()


def list_archived_auth_logs(user_id=None, start_at=None, end_at=None, limit=500):
    limit = max(1, min(int(limit), 5000))
    query = 'SELECT * FROM auth_logs_archive WHERE 1=1'
    params = []
    if user_id:
        query += ' AND user_id=?'
        params.append(user_id)
    if start_at is not None:
        query += ' AND occurred_at>=?'
        params.append(start_at)
    if end_at is not None:
        query += ' AND occurred_at<?'
        params.append(end_at)
    query += ' ORDER BY occurred_at DESC LIMIT ?'
    params.append(limit)
    with connect() as c:
        return c.execute(query, params).fetchall()


def archive_old_auth_logs(older_than_at):
    """Moves session/auth/sign-in-out events older than the cutoff into the 1-year backup
    table (auth_logs_archive) and removes them from the live table. See app/config.py
    auth_log_archive_after_days."""
    now = int(__import__('time').time())
    with connect() as c:
        rows = c.execute('SELECT * FROM auth_logs WHERE occurred_at<?', (older_than_at,)).fetchall()
        for row in rows:
            c.execute('''INSERT OR IGNORE INTO auth_logs_archive(id,occurred_at,event_type,success,user_id,identity,
                ip_address,user_agent,details,archived_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (row['id'], row['occurred_at'], row['event_type'], row['success'], row['user_id'],
                 row['identity'], row['ip_address'], row['user_agent'], row['details'], now))
        c.execute('DELETE FROM auth_logs WHERE occurred_at<?', (older_than_at,))
        return len(rows)


def purge_old_archived_auth_logs(older_than_at):
    """Permanently deletes archived events past the 3-year total retention window.
    See app/config.py auth_log_purge_after_days."""
    with connect() as c:
        return c.execute('DELETE FROM auth_logs_archive WHERE occurred_at<?', (older_than_at,)).rowcount


def delete_auth_logs_by_filter(target, start_at=None, end_at=None):
    """Admin-triggered cleanup ahead of the automatic schedule, scoped by date range and
    target table(s) — used for the custom/weekly/monthly/yearly cleanup filters."""
    deleted = {"live": 0, "archive": 0}
    with connect() as c:
        if target in ('live', 'both'):
            query = 'DELETE FROM auth_logs WHERE 1=1'
            params = []
            if start_at is not None:
                query += ' AND occurred_at>=?'
                params.append(start_at)
            if end_at is not None:
                query += ' AND occurred_at<?'
                params.append(end_at)
            deleted['live'] = c.execute(query, params).rowcount
        if target in ('archive', 'both'):
            query = 'DELETE FROM auth_logs_archive WHERE 1=1'
            params = []
            if start_at is not None:
                query += ' AND occurred_at>=?'
                params.append(start_at)
            if end_at is not None:
                query += ' AND occurred_at<?'
                params.append(end_at)
            deleted['archive'] = c.execute(query, params).rowcount
    return deleted



def delete_user_admin(user_id):
    with connect() as c:
        refs=c.execute("SELECT COUNT(*) FROM orders WHERE user_id=?",(user_id,)).fetchone()[0]
        if refs: return False
        c.execute("DELETE FROM customer_profiles WHERE user_id=?",(user_id,))
        c.execute("DELETE FROM auth_sessions WHERE user_id=?",(user_id,))
        c.execute("DELETE FROM users WHERE id=?",(user_id,))
        return True

def list_offers(active_public=False):
    now=int(__import__('time').time())
    with connect() as c:
        if active_public:
            return c.execute("SELECT * FROM offers WHERE status='active' AND (start_at IS NULL OR start_at<=?) AND (end_at IS NULL OR end_at>=?) ORDER BY priority,id",(now,now)).fetchall()
        return c.execute("SELECT * FROM offers ORDER BY priority,id").fetchall()

def save_offer(data, offer_id=None):
    now=int(__import__('time').time()); oid=offer_id or data['id']
    with connect() as c:
        exists=c.execute("SELECT 1 FROM offers WHERE id=?",(oid,)).fetchone()
        vals=(data['title'],data.get('slogan',''),data.get('description',''),data.get('offer_type','informational'),float(data.get('value',0)),data.get('code',''),data.get('scope','site'),data.get('target',''),data.get('image',''),data.get('cta_text',''),data.get('cta_link',''),data.get('placement','offers'),data.get('status','draft'),int(data.get('priority',100)),data.get('start_at'),data.get('end_at'),now,oid)
        if exists:
            c.execute("UPDATE offers SET title=?,slogan=?,description=?,offer_type=?,value=?,code=?,scope=?,target=?,image=?,cta_text=?,cta_link=?,placement=?,status=?,priority=?,start_at=?,end_at=?,updated_at=? WHERE id=?",vals)
        else:
            c.execute("INSERT INTO offers(id,title,slogan,description,offer_type,value,code,scope,target,image,cta_text,cta_link,placement,status,priority,start_at,end_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(oid,)+vals[:-1]+(now,))
    return oid

def delete_offer(offer_id):
    with connect() as c: c.execute("DELETE FROM offers WHERE id=?",(offer_id,))


def find_accounts_by_phone(phone):
    """Return every account owning this number; ambiguous numbers must never authenticate."""
    with connect() as c:
        rows = c.execute("SELECT id,name,email,username,phone,role,must_change_password FROM users WHERE phone=?", (phone,)).fetchall()
    accounts = [dict(row) for row in rows]
    admin = get_admin_profile()
    if admin.get('phone') == phone:
        accounts.append({'id':'admin', 'name':admin['name'], 'email':admin['email'], 'username':admin['username'], 'phone':phone, 'role':'admin', 'must_change_password':False})
    return accounts

def create_login_otp(otp_id, identity, user_id, email, phone, code_hash, created_at, expires_at):
    with connect() as c:
        c.execute("DELETE FROM login_otps WHERE expires_at<? OR used_at IS NOT NULL", (created_at,))
        c.execute("INSERT INTO login_otps(id,identity,user_id,email,phone,code_hash,created_at,expires_at) VALUES(?,?,?,?,?,?,?,?)",
                  (otp_id,identity.lower().strip(),user_id,email,phone,code_hash,created_at,expires_at))

def consume_login_otp(identity, code_hash, now):
    with connect() as c:
        row=c.execute("SELECT * FROM login_otps WHERE identity=? AND used_at IS NULL AND expires_at>=? ORDER BY created_at DESC LIMIT 1",
                      (identity.lower().strip(),now)).fetchone()
        if not row or row['code_hash'] != code_hash: return None
        c.execute("UPDATE login_otps SET used_at=? WHERE id=?",(now,row['id']))
        return row


def list_category_media():
    with connect() as c:
        return c.execute("SELECT * FROM catalog_category_media ORDER BY category COLLATE NOCASE").fetchall()

def save_category_media(category, image):
    now=int(__import__('time').time())
    with connect() as c:
        c.execute("INSERT INTO catalog_category_media(category,image,updated_at) VALUES(?,?,?) ON CONFLICT(category) DO UPDATE SET image=excluded.image,updated_at=excluded.updated_at", (category.strip(), image, now))
    return {"category":category.strip(),"image":image,"updated_at":now}

# Rich category management (additive; category remains referenced by catalog.category)
def list_category_settings():
    with connect() as c:
        return c.execute("SELECT * FROM catalog_category_media ORDER BY sort_order, category COLLATE NOCASE").fetchall()

def save_category_settings(category, data):
    now=int(__import__('time').time()); category=category.strip()
    with connect() as c:
        row=c.execute("SELECT category FROM catalog_category_media WHERE category=?",(category,)).fetchone()
        if row:
            c.execute("UPDATE catalog_category_media SET display_name=?,description=?,active=?,sort_order=?,updated_at=? WHERE category=?",(data.get('display_name') or category,data.get('description',''),int(bool(data.get('active',True))),int(data.get('sort_order',100)),now,category))
        else:
            c.execute("INSERT INTO catalog_category_media(category,image,display_name,description,active,sort_order,updated_at,category_id) VALUES(?,?,?,?,?,?,?,?)",(category,'',data.get('display_name') or category,data.get('description',''),int(bool(data.get('active',True))),int(data.get('sort_order',100)),now,uuid.uuid4().hex))

def rename_category(old, new):
    old=old.strip(); new=new.strip(); now=int(__import__('time').time())
    if not old or not new: raise ValueError("Category name is required")
    with connect() as c:
        if old == new: return 0
        # Protect against silently merging two categories, including case-insensitive collisions.
        collision=c.execute("SELECT category FROM catalog WHERE lower(category)=lower(?) AND category<>? LIMIT 1",(new,old)).fetchone()
        media_collision=c.execute("SELECT category FROM catalog_category_media WHERE lower(category)=lower(?) AND category<>? LIMIT 1",(new,old)).fetchone()
        if collision or media_collision: raise ValueError("A different category with that name already exists")
        count=c.execute("SELECT COUNT(*) FROM catalog WHERE category=?",(old,)).fetchone()[0]
        c.execute("UPDATE catalog SET category=?,updated_at=? WHERE category=?",(new,now,old))
        c.execute("UPDATE catalog_category_media SET category=?,display_name=CASE WHEN display_name=? THEN ? ELSE display_name END,updated_at=? WHERE category=?",(new,old,new,now,old))
        return count

def delete_category_settings(category):
    with connect() as c:
        # Deletion is protected while ANY product (live, coming soon or archived) references the category.
        count=c.execute("SELECT COUNT(*) FROM catalog WHERE category=?",(category,)).fetchone()[0]
        if count: return False
        c.execute("DELETE FROM catalog_category_media WHERE category=?",(category,)); return True


def _category_row_by_id(c, category_id):
    return c.execute("SELECT * FROM catalog_category_media WHERE category_id=?",(category_id,)).fetchone()

def category_diagnostics():
    with connect() as c:
        rows=c.execute("""SELECT m.*, (SELECT COUNT(*) FROM catalog p WHERE p.category=m.category) product_count FROM catalog_category_media m ORDER BY lower(m.category),m.category""").fetchall()
        items=[dict(r) for r in rows]; groups={}
        for d in items:
            d["normalized_name"]=unquote(d["category"]).strip().casefold()
            groups.setdefault(d["normalized_name"],[]).append(d["category_id"])
        for d in items:
            d["duplicate"]=len(groups[d["normalized_name"]])>1
            d["duplicate_group_ids"]=groups[d["normalized_name"]]
        return items

def update_category_by_id(category_id,data):
    now=int(__import__("time").time())
    with connect() as c:
        row=_category_row_by_id(c,category_id)
        if not row: raise ValueError("Category no longer exists. Refresh Categories and try again.")
        old=row["category"]; new=(data.get("new_category") or data.get("display_name") or old).strip()
        if not new: raise ValueError("Category name is required")
        collision=c.execute("SELECT category_id FROM catalog_category_media WHERE lower(category)=lower(?) AND category_id<>? LIMIT 1",(new,category_id)).fetchone()
        if collision: raise ValueError("Another category already uses that name. Use Merge/Reassign for duplicates.")
        count=c.execute("SELECT COUNT(*) FROM catalog WHERE category=?",(old,)).fetchone()[0]
        if new!=old: c.execute("UPDATE catalog SET category=?,updated_at=? WHERE category=?",(new,now,old))
        c.execute("UPDATE catalog_category_media SET category=?,display_name=?,description=?,active=?,sort_order=?,updated_at=? WHERE category_id=?",(new,data.get("display_name") or new,data.get("description",""),int(bool(data.get("active",True))),int(data.get("sort_order",100)),now,category_id))
        return {"category_id":category_id,"category":new,"products_updated":count}

def save_category_image_by_id(category_id,image):
    now=int(__import__("time").time())
    with connect() as c:
        row=_category_row_by_id(c,category_id)
        if not row: raise ValueError("Category no longer exists. Refresh Categories and try again.")
        c.execute("UPDATE catalog_category_media SET image=?,updated_at=? WHERE category_id=?",(image,now,category_id))
        return {"category_id":category_id,"category":row["category"],"image":image}

def delete_category_by_id(category_id):
    with connect() as c:
        row=_category_row_by_id(c,category_id)
        if not row: raise ValueError("Category no longer exists")
        count=c.execute("SELECT COUNT(*) FROM catalog WHERE category=?",(row["category"],)).fetchone()[0]
        if count:return {"deleted":False,"product_count":count,"category":row["category"]}
        c.execute("DELETE FROM catalog_category_media WHERE category_id=?",(category_id,))
        return {"deleted":True,"product_count":0,"category":row["category"]}

def merge_category_by_id(source_id,target_id):
    if source_id==target_id: raise ValueError("Source and target category must be different")
    now=int(__import__("time").time())
    with connect() as c:
        source=_category_row_by_id(c,source_id); target=_category_row_by_id(c,target_id)
        if not source or not target: raise ValueError("Source or target category no longer exists")
        moved=c.execute("SELECT COUNT(*) FROM catalog WHERE category=?",(source["category"],)).fetchone()[0]
        c.execute("UPDATE catalog SET category=?,updated_at=? WHERE category=?",(target["category"],now,source["category"]))
        c.execute("UPDATE catalog_category_media SET image=?,description=?,updated_at=? WHERE category_id=?",(target["image"] or source["image"],target["description"] or source["description"],now,target_id))
        c.execute("DELETE FROM catalog_category_media WHERE category_id=?",(source_id,))
        return {"status":"merged","source":source["category"],"target":target["category"],"products_moved":moved}

def import_catalog_atomic(items, authoritative=False):
    # Validated atomic batch; blank existing images are preserved. Authoritative mode archives missing rows.
    now=int(__import__('time').time()); ins=upd=preserved=archived=0
    incoming={str(x['id']) for x in items}
    with connect() as c:
        for data in items:
            pid=data['id']; existing=c.execute('SELECT * FROM catalog WHERE id=?',(pid,)).fetchone()
            image=(data.get('image') or '').strip()
            if existing and not image:
                image=existing['image'] or ''; preserved+=1
            if existing:
                c.execute('''UPDATE catalog SET name=?,category=?,state=?,price=?,mrp=?,unit=?,description=?,image=?,parent_url=?,active=?,status=?,updated_at=? WHERE id=?''',
                          (data['name'],data['category'],data['state'],data['price'],data['mrp'],data['unit'],data['description'],image,data.get('parent_url',''),int(data.get('active',True)),data.get('status','live'),now,pid)); upd+=1
            else:
                c.execute('''INSERT INTO catalog(id,name,category,state,price,mrp,unit,description,image,parent_url,active,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                          (pid,data['name'],data['category'],data['state'],data['price'],data['mrp'],data['unit'],data['description'],image,data.get('parent_url',''),int(data.get('active',True)),data.get('status','live'),now,now)); ins+=1
        if authoritative:
            rows=c.execute("SELECT id FROM catalog WHERE active=1 OR status<>'archived'").fetchall()
            missing=[r['id'] for r in rows if str(r['id']) not in incoming]
            if missing:
                c.executemany("UPDATE catalog SET active=0,status='archived',updated_at=? WHERE id=?",[(now,p) for p in missing]); archived=len(missing)
    return {'inserted':ins,'updated':upd,'images_preserved':preserved,'archived_missing':archived}


def force_delete_categories(category_ids, strategy='reassign', target_category_id=''):
    # Administrator-only repository operation; caller creates a pre-operation snapshot.
    now=int(__import__('time').time())
    with connect() as c:
        sources=[]
        for cid in category_ids:
            row=c.execute("SELECT * FROM catalog_category_media WHERE category_id=?",(cid,)).fetchone()
            if row: sources.append(row)
        if not sources: return {'categories_deleted':0,'products_affected':0}
        target=None
        if strategy=='reassign':
            target=c.execute("SELECT * FROM catalog_category_media WHERE category_id=?",(target_category_id,)).fetchone()
            if not target: raise ValueError('A valid target category is required for reassignment')
            if target_category_id in category_ids: raise ValueError('Target category cannot also be deleted')
        affected=0
        for src in sources:
            count=c.execute("SELECT COUNT(*) FROM catalog WHERE category=?",(src['category'],)).fetchone()[0]; affected+=count
            if strategy=='reassign':
                c.execute("UPDATE catalog SET category=?,updated_at=? WHERE category=?",(target['category'],now,src['category']))
            elif strategy=='archive':
                # Keep referential meaning by moving archived products to a retained system category.
                unc=c.execute("SELECT * FROM catalog_category_media WHERE lower(category)='uncategorized' LIMIT 1").fetchone()
                if not unc:
                    uid=__import__('uuid').uuid4().hex
                    c.execute("INSERT INTO catalog_category_media(category,image,updated_at,display_name,description,active,sort_order,category_id) VALUES('Uncategorized','',?,'Uncategorized','Products retained after category cleanup',0,9999,?)",(now,uid))
                c.execute("UPDATE catalog SET category='Uncategorized',active=0,status='archived',updated_at=? WHERE category=?",(now,src['category']))
            elif strategy=='delete_products':
                c.execute("DELETE FROM catalog WHERE category=?",(src['category'],))
            else: raise ValueError('Invalid force-delete strategy')
            c.execute("DELETE FROM catalog_category_media WHERE category_id=?",(src['category_id'],))
        return {'categories_deleted':len(sources),'products_affected':affected,'strategy':strategy}


def get_catalog_template_config():
    with connect() as c:
        row=c.execute("SELECT value FROM site_content WHERE `key`='__catalog_template_fields'").fetchone()
        if not row: return []
        try: return __import__('json').loads(row['value'])
        except Exception: return []

def save_catalog_template_config(fields):
    now=int(__import__('time').time()); value=__import__('json').dumps(fields)
    with connect() as c:
        c.execute("INSERT INTO site_content(`key`,value,image,link,active,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(`key`) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",('__catalog_template_fields',value,'','',0,now))


def set_order_gateway_reference(order_id, gateway_reference):
    # Legacy compatibility column; new provider-neutral references also live in payment_transactions.
    with connect() as c:
        c.execute('UPDATE orders SET razorpay_order_id=? WHERE id=?', (gateway_reference, order_id))

def create_payment_transaction(tx_id, order_id, provider, provider_order_id, amount_paise, currency='INR', status='created',
                               payment_session_id='', environment='', idempotency_key='', is_test=False, gateway_status=''):
    now=int(__import__('time').time())
    with connect() as c:
        c.execute("""INSERT INTO payment_transactions(id,order_id,provider,provider_order_id,payment_session_id,amount_paise,currency,status,environment,idempotency_key,is_test,gateway_status,created_at,updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (tx_id,order_id,provider,provider_order_id or '',payment_session_id or '',int(amount_paise),currency,status,environment,idempotency_key or '',int(bool(is_test)),gateway_status or '',now,now))

def update_payment_transaction(tx_id, *, status=None, provider_payment_id=None, gateway_status=None, verified=False):
    fields=[]; values=[]
    if status is not None: fields.append('status=?'); values.append(status)
    if provider_payment_id is not None: fields.append('provider_payment_id=?'); values.append(provider_payment_id)
    if gateway_status is not None: fields.append('gateway_status=?'); values.append(gateway_status)
    fields.append('updated_at=?'); values.append(int(__import__('time').time()))
    if verified: fields.append('verified_at=?'); values.append(int(__import__('time').time()))
    values.append(tx_id)
    with connect() as c: c.execute('UPDATE payment_transactions SET '+','.join(fields)+' WHERE id=?', values)

def get_payment_transaction_by_provider_order(provider, provider_order_id):
    with connect() as c:
        return c.execute('SELECT * FROM payment_transactions WHERE provider=? AND provider_order_id=? ORDER BY created_at DESC LIMIT 1',(provider,provider_order_id)).fetchone()

def list_payment_transactions(limit=200, is_test=None):
    limit=max(1,min(int(limit),1000))
    with connect() as c:
        if is_test is None: return c.execute('SELECT * FROM payment_transactions ORDER BY created_at DESC LIMIT ?',(limit,)).fetchall()
        return c.execute('SELECT * FROM payment_transactions WHERE is_test=? ORDER BY created_at DESC LIMIT ?',(int(bool(is_test)),limit)).fetchall()
