"""Reusable mechanics for a service-owned identity store.

The caller supplies its own SQLite connection. No database, user, role, secret or
session is shared between services.
"""
import secrets, time
from .security import hash_password, verify_password

SESSION_IDLE_SECONDS=4*60*60
SESSION_LIFETIME_SECONDS=7*24*60*60

def init_identity(c, prefix: str, admin_email: str, admin_password: str):
    c.executescript(f"""
    CREATE TABLE IF NOT EXISTS {prefix}_users(
      id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,name TEXT NOT NULL DEFAULT '',
      password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'user',blocked INTEGER NOT NULL DEFAULT 0,
      must_change_password INTEGER NOT NULL DEFAULT 0,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS {prefix}_sessions(
      token TEXT PRIMARY KEY,user_id TEXT NOT NULL,role TEXT NOT NULL,created_at INTEGER NOT NULL,
      last_activity_at INTEGER NOT NULL,expires_at INTEGER NOT NULL,logged_out_at INTEGER,
      ip_address TEXT DEFAULT '',user_agent TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS {prefix}_auth_logs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,success INTEGER NOT NULL,
      user_id TEXT DEFAULT '',login TEXT DEFAULT '',created_at INTEGER NOT NULL,ip_address TEXT DEFAULT '',detail TEXT DEFAULT '');
    """)
    now=int(time.time())
    existing=c.execute(f"SELECT id FROM {prefix}_users WHERE role='admin' ORDER BY created_at LIMIT 1").fetchone()
    if not existing:
        c.execute(f"INSERT INTO {prefix}_users(id,email,name,password_hash,role,blocked,must_change_password,created_at,updated_at) VALUES(?,?,?,?, 'admin',0,0,?,?)",
                  (f'__{prefix}_admin__',admin_email.strip().lower(),'Administrator',hash_password(admin_password),now,now))

def login(connect,prefix,email,password,request=None):
    now=int(time.time()); email=email.strip().lower()
    with connect() as c:
        u=c.execute(f"SELECT * FROM {prefix}_users WHERE lower(email)=?",(email,)).fetchone()
        ok=bool(u) and not int(u['blocked'] or 0) and verify_password(password,u['password_hash'])
        c.execute(f"INSERT INTO {prefix}_auth_logs(event_type,success,user_id,login,created_at,ip_address,detail) VALUES('login',?,?,?,?,?,?)",
                  (int(ok),u['id'] if u else '',email,now,request.client.host if request and request.client else '','success' if ok else 'invalid credentials'))
        if not ok: return None
        token=secrets.token_urlsafe(32)
        c.execute(f"INSERT INTO {prefix}_sessions(token,user_id,role,created_at,last_activity_at,expires_at,ip_address,user_agent) VALUES(?,?,?,?,?,?,?,?)",
                  (token,u['id'],u['role'],now,now,now+SESSION_LIFETIME_SECONDS,request.client.host if request and request.client else '',request.headers.get('user-agent','')[:500] if request else ''))
        return token

def session(connect,prefix,token):
    if not token: return None
    now=int(time.time())
    with connect() as c:
        s=c.execute(f"SELECT * FROM {prefix}_sessions WHERE token=? AND logged_out_at IS NULL AND expires_at>?",(token,now)).fetchone()
        if not s or now-int(s['last_activity_at'])>SESSION_IDLE_SECONDS: return None
        u=c.execute(f"SELECT * FROM {prefix}_users WHERE id=?",(s['user_id'],)).fetchone()
        if not u or int(u['blocked'] or 0): return None
        c.execute(f"UPDATE {prefix}_sessions SET last_activity_at=? WHERE token=?",(now,token))
        return {'id':u['id'],'email':u['email'],'name':u['name'],'role':u['role'],'must_change_password':bool(u['must_change_password'])}

def logout(connect,prefix,token):
    with connect() as c: c.execute(f"UPDATE {prefix}_sessions SET logged_out_at=? WHERE token=?",(int(time.time()),token))

def change_password(connect,prefix,user_id,current,new):
    with connect() as c:
        u=c.execute(f"SELECT * FROM {prefix}_users WHERE id=?",(user_id,)).fetchone()
        if not u or not verify_password(current,u['password_hash']): return False
        c.execute(f"UPDATE {prefix}_users SET password_hash=?,must_change_password=0,updated_at=? WHERE id=?",(hash_password(new),int(time.time()),user_id)); return True

def list_users(connect,prefix):
    with connect() as c: return [dict(r) for r in c.execute(f"SELECT id,email,name,role,blocked,must_change_password,created_at,updated_at FROM {prefix}_users ORDER BY name,email")]

def create_user(connect,prefix,email,name,password,role):
    uid=f'{prefix}_{secrets.token_hex(8)}'; now=int(time.time())
    with connect() as c: c.execute(f"INSERT INTO {prefix}_users(id,email,name,password_hash,role,blocked,must_change_password,created_at,updated_at) VALUES(?,?,?,?,?,0,0,?,?)",(uid,email.strip().lower(),name.strip(),hash_password(password),role,now,now))
    return uid

def update_access(connect,prefix,user_id,role,blocked):
    with connect() as c:
        c.execute(f"UPDATE {prefix}_users SET role=?,blocked=?,updated_at=? WHERE id=?",(role,int(blocked),int(time.time()),user_id))
        if blocked: c.execute(f"UPDATE {prefix}_sessions SET logged_out_at=? WHERE user_id=? AND logged_out_at IS NULL",(int(time.time()),user_id))
        return c.total_changes>0


def reset_password(connect,prefix,user_id,new_password):
    with connect() as c:
        c.execute(f"UPDATE {prefix}_users SET password_hash=?,must_change_password=1,updated_at=? WHERE id=?",(hash_password(new_password),int(time.time()),user_id))
        changed=c.total_changes>0
        if changed: c.execute(f"UPDATE {prefix}_sessions SET logged_out_at=? WHERE user_id=? AND logged_out_at IS NULL",(int(time.time()),user_id))
        return changed

def delete_user(connect,prefix,user_id):
    with connect() as c:
        u=c.execute(f"SELECT role FROM {prefix}_users WHERE id=?",(user_id,)).fetchone()
        if not u or u['role']=='admin': return False
        c.execute(f"DELETE FROM {prefix}_sessions WHERE user_id=?",(user_id,))
        c.execute(f"DELETE FROM {prefix}_users WHERE id=?",(user_id,)); return True
