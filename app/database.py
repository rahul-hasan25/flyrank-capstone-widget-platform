import sqlite3
import os
from contextlib import contextmanager
from typing import Generator
from app.config import settings

def get_db_path() -> str:
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "")
        return os.path.abspath(path)
    return "widget_platform.db"

@contextmanager
def get_db(db_path: str = None) -> Generator[sqlite3.Connection, None, None]:
    target_path = db_path or get_db_path()
    conn = sqlite3.connect(target_path, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db(db_path: str = None) -> None:
    target_path = db_path or get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with get_db(target_path) as conn:
        cursor = conn.cursor()
        
        # Tenants table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                api_key TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Widgets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS widgets (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                fields_schema TEXT NOT NULL,
                button_text TEXT DEFAULT 'Submit',
                display_options TEXT DEFAULT '{}',
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
            );
        """)
        
        # Submissions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id TEXT PRIMARY KEY,
                widget_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                origin TEXT,
                geo_country TEXT,
                geo_city TEXT,
                geo_region TEXT,
                geo_provider TEXT,
                idempotency_key TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (widget_id) REFERENCES widgets(id) ON DELETE CASCADE,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
            );
        """)
        
        # Side effect logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS side_effect_logs (
                id TEXT PRIMARY KEY,
                submission_id TEXT NOT NULL,
                effect_type TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Performance & isolation indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_widgets_tenant ON widgets(tenant_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_widget ON submissions(widget_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_tenant_created ON submissions(tenant_id, created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submissions_idempotency ON submissions(widget_id, idempotency_key);")
