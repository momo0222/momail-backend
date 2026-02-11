import asyncio
import os
from datetime import datetime
from sqlalchemy.orm import Session

from app.services.gmail_client import GmailClient
from app.services.demo_gmail_client import DemoGmailClient
from app.models.email import Email
from app.models.action import Action
from app.database import SessionLocal
from app.models.config import AgentConfig
from app.core.config import settings

class AgentService:
    """
    Background service that:
    1. Polls Gmail for new emails
    2. Classifies them
    3. Decides what actions to take
    4. Saves to database for user approval
    """

    def __init__(self):
        use_demo = settings.demo_mode
        print(f"Using DEMO_MODE: {use_demo}")
        self.gmail_client = DemoGmailClient() if use_demo else GmailClient()
        self.seen_emails = set()
        self.running = False
    
    def get_config(self, db: Session) -> AgentConfig:
        """
        Fetch the agent configuration from the database.
        If none exists, create a default one.
        """
        config = db.query(AgentConfig).filter(AgentConfig.id == 1).first()
        if not config:
            config = AgentConfig()
            db.add(config)
            db.commit()
            db.refresh(config)
        return config
    
    def check_for_new_emails(self, db: Session) -> list:
        """
        Check Gmail for new emails that we haven't processed

        Returns a list of email IDs that are new
        """
        if settings.demo_mode:
            has_action=False
            unread = db.query(Email).filter(Email.processed == False).all()
            new = []
            for e in self.seen_emails:
               has_action = db.query(Action).filter(Action.email_id == e.id).first()
            if not has_action:
                new.append(e.id)
            return new
        unread = self.gmail_client.list_messages(max_results=100, query="is:unread")

        new_emails = []
        for msg in unread:
            email_id = msg["id"]

            # skip if already in db
            existing = db.query(Email).filter(Email.id == email_id).first()
            if existing:
                continue

            # skip if already seen in this session
            if email_id in self.seen_emails:
                continue
                
            new_emails.append(email_id)
        
        return new_emails

    def process_email(self, email_id: str, db: Session):
        """
        Process a single email:
        1. Fetch from Gmail
        2. Parse and classify
        3. Save to DB
        4. Create action
        """
        print(f"Processing email: {email_id}")

        # fetch from gmail
        if settings.demo_mode:
            email = db.query(Email).filter(Email.id == email_id).first()
            parsed_email = {
                "id": email.id, #type:ignore
                "threadId": email.thread_id,#type:ignore
                "from": email.from_address,#type:ignore
                "name": email.from_name,#type:ignore
                "from-raw": email.from_raw,#type:ignore
                "to": email.to_address,#type:ignore
                "subject": email.subject,#type:ignore
                "snippet": email.snippet,#type:ignore
                "body": email.body,#type:ignore
            }
        else:
            raw_email = self.gmail_client.get_message(email_id)
            parsed_email = self.gmail_client.parse_message(raw_email)

        # classify with AI
        classification = self.gmail_client.classify_email(parsed_email)

        print(f"    From: {parsed_email['from']}")
        print(f"    Subject: {parsed_email['subject']}")
        print(f"    Classification: {classification}")

        if not settings.demo_mode:
            db_email = Email(
                id=parsed_email["id"],
                thread_id=parsed_email["threadId"],
                from_address=parsed_email["from"],
                from_name=parsed_email["name"],
                from_raw=parsed_email["from-raw"],
                to_address=parsed_email.get("to", ""),
                subject=parsed_email["subject"],
                snippet=parsed_email.get("snippet", ""),
                body=parsed_email.get("body", ""),
                classification=classification,
                processed=False,
            )
            db.add(db_email)
            db.commit()
        else:
            # demo mode: update existing record
            email = db.query(Email).filter(Email.id == parsed_email["id"]).first()
            email.classification = classification #type:ignore
            db.commit()

        
        # decide action
        action = self.decide_action(parsed_email, classification, db)

        db_action = Action(
            email_id=parsed_email["id"],
            action_type=action['type'],
            suggested_reply=action.get('message', None),
            reason=action['reason'],
            status='pending'
        )

        db.add(db_action)
        db.commit()

        print(f"    Saved! Action: {action['type']} - {action['reason']}")

        # mark as seen
        self.seen_emails.add(email_id)

    
    def decide_action(self, parsed_email: dict, classification: str, db: Session) -> dict:
        """
        Decide what action to take based on classification
        
        Uses whitelist/blacklist logic from config, return dict with
        1. type: reply, archive, notify, skip
        2. message: suggested reply (if type is reply)
        3. reason: explanation for the action
        """
        sender = parsed_email['from'].lower()
        
        # Whitelist/Blacklist (copy from your config or make configurable)
        config = self.get_config(db)
        AUTO_REPLY_WHITELIST = config.get_whitelist()
        AUTO_REPLY_BLACKLIST = config.get_blacklist()
        
        # Check blacklist first
        if any(blocked in sender for blocked in AUTO_REPLY_BLACKLIST):
            return {
                'type': 'notify',
                'reason': f'Blacklisted sender: {sender}'
            }
        
        # Check if whitelisted
        is_whitelisted = any(allowed in sender for allowed in AUTO_REPLY_WHITELIST)
        
        # Whitelisted senders get special treatment
        if is_whitelisted:
            if classification in ['routine', 'spam', 'personal']:
                # Auto-reply even if spam/personal (they're trusted)
                reply = self.gmail_client.generate_smart_reply(parsed_email)
                return {
                    'type': 'reply',
                    'message': reply,
                    'reason': 'Whitelisted sender - auto-reply'
                }
            else:  # urgent
                return {
                    'type': 'notify',
                    'reason': 'Urgent email from whitelisted sender'
                }
        
        # Non-whitelisted: use classification
        if classification == 'urgent':
            return {
                'type': 'notify',
                'reason': 'Urgent email requiring immediate attention'
            }
        
        elif classification == 'routine':
            return {
                'type': 'notify',
                'reason': 'Routine email from non-whitelisted sender'
            }
        
        elif classification == 'spam':
            return {
                'type': 'archive',
                'reason': 'Classified as spam'
            }
        
        elif classification == 'personal':
            return {
                'type': 'notify',
                'reason': 'Personal email'
            }
        
        else:
            return {
                'type': 'notify',
                'reason': f'Unknown classification: {classification}'
            }
    
    async def run_loop(self, check_interval: int = 60):
        """
        Main agent loop - runs continuously in the background

        Args:
            check_interval: seconds between checks
        """
        print(f"Agent starting...(check every {check_interval}s)")
        self.running = True

        while self.running:
            try:
                # create db session
                db = SessionLocal()
                try:
                    new_emails = self.check_for_new_emails(db)
                    if new_emails:
                        print(f"Found {len(new_emails)} new emails.")

                        for email_id in new_emails:
                            try:
                                self.process_email(email_id, db)
                            except Exception as e:
                                print(f"Error processing email {email_id}: {e}")
                    else:
                        print(f"No new emails found at {datetime.now().strftime('%H:%M:%S')}.")
                finally:
                    db.close()
            

                await asyncio.sleep(check_interval)
            except Exception as e:
                print(f"Error in agent loop: {e}")
                await asyncio.sleep(check_interval)
    
    def stop(self):
        """
        Stop the agent loop
        """
        self.running = False
        print("Agent stopping...")

agent = AgentService()