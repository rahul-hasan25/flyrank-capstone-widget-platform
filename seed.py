import json
import uuid
from app.database import init_db, get_db

def seed_database():
    print("Initializing database tables...")
    init_db()

    with get_db() as conn:
        cursor = conn.cursor()

        # Clear existing data for a clean reproducible seed
        cursor.execute("DELETE FROM side_effect_logs;")
        cursor.execute("DELETE FROM submissions;")
        cursor.execute("DELETE FROM widgets;")
        cursor.execute("DELETE FROM tenants;")

        # 1. Seed Tenant A
        tenant_a_id = "tenant_acme"
        tenant_a_key = "sk_live_demo_12345"
        cursor.execute(
            "INSERT INTO tenants (id, name, api_key) VALUES (?, ?, ?)",
            (tenant_a_id, "Acme Corporation", tenant_a_key)
        )

        # 2. Seed Tenant B
        tenant_b_id = "tenant_globex"
        tenant_b_key = "sk_live_globex_99999"
        cursor.execute(
            "INSERT INTO tenants (id, name, api_key) VALUES (?, ?, ?)",
            (tenant_b_id, "Globex International", tenant_b_key)
        )

        # 3. Seed Widgets for Tenant A
        widget_a1_fields = [
            {"name": "name", "label": "Full Name", "type": "text", "required": True},
            {"name": "email", "label": "Work Email", "type": "email", "required": True}
        ]
        widget_a1_disp = {
            "position": "bottom-right",
            "theme_color": "#2563eb",
            "headline_color": "#111827",
            "trigger": "immediate",
            "delay_seconds": 0
        }
        cursor.execute(
            """
            INSERT INTO widgets (
                id, tenant_id, name, type, title, description,
                fields_schema, button_text, display_options, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                "wgt_demo_signup", tenant_a_id, "Acme Product Signup", "signup_form",
                "Join the Acme Cloud Beta", "Sign up now for early access and priority updates.",
                json.dumps(widget_a1_fields), "Claim My Spot", json.dumps(widget_a1_disp)
            )
        )

        widget_a2_fields = [
            {"name": "email", "label": "Email Address", "type": "email", "required": True}
        ]
        widget_a2_disp = {
            "position": "bottom-left",
            "theme_color": "#059669",
            "headline_color": "#064e3b",
            "trigger": "delay",
            "delay_seconds": 3
        }
        cursor.execute(
            """
            INSERT INTO widgets (
                id, tenant_id, name, type, title, description,
                fields_schema, button_text, display_options, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                "wgt_demo_cta", tenant_a_id, "Newsletter Popover", "popover",
                "Stay in the Loop", "Get weekly engineering insights straight to your inbox.",
                json.dumps(widget_a2_fields), "Subscribe", json.dumps(widget_a2_disp)
            )
        )

        # 4. Seed Widget for Tenant B
        widget_b1_fields = [
            {"name": "name", "label": "Your Name", "type": "text", "required": True},
            {"name": "email", "label": "Contact Email", "type": "email", "required": True},
            {"name": "company", "label": "Company", "type": "text", "required": False}
        ]
        widget_b1_disp = {
            "position": "bottom-right",
            "theme_color": "#7c3aed",
            "headline_color": "#4c1d95",
            "trigger": "immediate",
            "delay_seconds": 0
        }
        cursor.execute(
            """
            INSERT INTO widgets (
                id, tenant_id, name, type, title, description,
                fields_schema, button_text, display_options, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                "wgt_globex_contact", tenant_b_id, "Enterprise Inquiry", "contact_form",
                "Talk to Globex Sales", "Reach our worldwide sales team.",
                json.dumps(widget_b1_fields), "Request Demo", json.dumps(widget_b1_disp)
            )
        )

        # 5. Seed Submissions for Tenant A
        submissions_data = [
            ("Alice Smith", "alice@example.com", "United States", "New York", "New York", "ip-api.com"),
            ("Bob Jones", "bob@example.com", "United Kingdom", "London", "England", "ip-api.com"),
            ("Charlie Brown", "charlie@example.com", "Germany", "Berlin", "Berlin", "ipapi.co")
        ]
        for name, email, country, city, region, provider in submissions_data:
            sub_id = f"sub_{uuid.uuid4().hex[:12]}"
            payload = json.dumps({"name": name, "email": email})
            cursor.execute(
                """
                INSERT INTO submissions (
                    id, widget_id, tenant_id, payload, ip_address,
                    user_agent, origin, geo_country, geo_city,
                    geo_region, geo_provider, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sub_id, "wgt_demo_signup", tenant_a_id, payload, "198.51.100.1",
                    "Mozilla/5.0", "http://localhost:5500", country, city,
                    region, provider, None
                )
            )

    print("Database seeding completed successfully.")
    print("--------------------------------------------------")
    print("Tenant A (Acme Corp):")
    print(f"  API Key:   {tenant_a_key}")
    print("  Widget ID: wgt_demo_signup")
    print("Tenant B (Globex):")
    print(f"  API Key:   {tenant_b_key}")
    print("  Widget ID: wgt_globex_contact")
    print("--------------------------------------------------")

if __name__ == "__main__":
    seed_database()
