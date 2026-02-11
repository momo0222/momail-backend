from app.core.config import settings
from app.services.gmail_client import GmailClient
from app.services.demo_gmail_client import DemoGmailClient

def get_gmail_client():
    if settings.demo_mode:
        return DemoGmailClient()
    return GmailClient()