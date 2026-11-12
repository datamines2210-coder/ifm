from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Indian Family Market"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8020
    database_url: str = "sqlite:///./indian_family_market.db"
    log_level: str = "INFO"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    # Cashfree Payment Gateway (primary). Credentials remain server-side only.
    cashfree_environment: str = "sandbox"  # sandbox | production
    cashfree_app_id: str = ""
    cashfree_secret_key: str = ""
    cashfree_api_version: str = "2025-01-01"
    cashfree_sandbox_base_url: str = "https://sandbox.cashfree.com/pg"
    cashfree_production_base_url: str = "https://api.cashfree.com/pg"
    cashfree_return_url: str = ""
    cashfree_notify_url: str = ""
    cashfree_health_cache_seconds: int = 30
    # Regional 3PL courier partner (primary dispatch channel); blank means no partner
    # is configured yet, so DispatchService always falls back to direct office courier.
    courier_partner_api_key: str = ""
    # Auth/session log lifecycle: live for 1 year, then archived for the next 3 years,
    # for 4 years total retention. Admins can also purge/export earlier via filters.
    auth_log_archive_after_days: int = 365
    auth_log_purge_after_days: int = 365 * 4
    alert_webhook_url: str = ""
    parent_catalog_url: str = "https://theindianfamily.com/"
    # Canonical public origin used by Phase 3 SEO delivery; no request Host trust.
    seo_public_base_url: str = "https://theindianfamily.shop"
    auth_secret: str = "change-this-development-secret"
    admin_email: str = "datamines2210@gmail.com"
    admin_username: str = "admin"
    admin_password: str = "!Hard2ges"
    admin_phone: str = ""
    otp_expiry_seconds: int = 300
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    sms_webhook_url: str = ""
    sms_webhook_token: str = ""
    whatsapp_number: str = "+91 86043 03030"
    whatsapp_message: str = "Hi! I have a question about your services."
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
