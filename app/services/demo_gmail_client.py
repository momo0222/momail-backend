import uuid
from datetime import datetime
from typing import List
from openai import OpenAI
from app.core.config import settings


client = OpenAI(api_key=settings.openai_api_key)


class DemoGmailClient:
    def __init__(self):
        self.from_address = "demo@momail.com"
        self._emails={} #id -> email dict
        self._unread_ids=set()
        self.sent = []

    def simulate_incoming_email(self, from_addr: str, name: str, subject: str, body:str):
        email_id = str(uuid.uuid4())

        email = {
            "id": email_id,
            "threadId": str(uuid.uuid4()),
            "from": from_addr.lower(),
            "name": name,
            "from-raw": f"{name} <{from_addr}>",
            "to": self.from_address,
            "subject": subject,
            "snippet": body[:120],
            "body": body,
            "date": datetime.now().isoformat()
        }
        self._emails[email_id] = email
        self._unread_ids.add(email_id)

    def list_messages(self, max_results=10, query: str = '') -> List[dict]:
        print("DEMO unread ids:", self._unread_ids)
        # Simulate unread filter
        if "is:unread" in query:
            ids = list(self._unread_ids)
        else:
            ids = list(self._emails.keys())
        return [{"id": eid} for eid in ids[:max_results]]

    def get_message(self, message_id: str) -> dict:
        return self._emails[message_id]

    def parse_message(self, raw: dict) -> dict:
        return raw

    def mark_as_read(self, message_id: str):
        self._unread_ids.discard(message_id)

    def archive(self, message_id: str):
        self._unread_ids.discard(message_id)

    def generate_smart_reply(self, parsed_email: dict) -> str:
        """Generate a single, contextually appropriate reply with tone support"""
        
        tone = parsed_email.get('tone', 'professional')
        custom_instructions = parsed_email.get('instructions', '')
        # Tone mappings
        tone_instructions = {
            'professional': 'Write a professional and polite reply.',
            'casual': 'Write a casual and friendly reply.',
            'friendly': 'Write a warm and friendly reply.',
            'brief': 'Write a very brief and concise reply (2-3 sentences max).',
        }
        tone_instruction = tone_instructions.get(tone, tone_instructions["professional"])
        prompt = f"""Generate ONLY the body of an email reply. Do NOT include subject line or headers.

        From: {parsed_email['from']}
        Subject: {parsed_email['subject']}
        Body: {parsed_email['body']}

        {tone_instruction}
        {custom_instructions}

        Based on the sender and content, write a helpful reply. Keep it concise but helpful. 
        Write ONLY the reply body text with appropriate tone. Start directly with the greeting."""

        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt
        )
    
        return response.output_text


    def classify_email(self, parsed_email: dict) -> str:
        """Classify email as urgent, personal, routine, or spam

        :param self: this
        :param parsed_email: Parsed email dict with subject, from, and snippet
        :type parsed_email: dict
        :return: Classification of the email as either 'urgent', 'personal', 'routine', or 'spam'
        :rtype: str
        """
        prompt = f"""Classify this email as one of: urgent, personal, routine, or spam

                Subject: {parsed_email['subject']}
                From: {parsed_email['from']}
                Preview: {parsed_email['snippet']}

                Respond with just one word: urgent, personal, routine, or spam"""
        response = client.responses.create(
            model="gpt-4o-mini",
            input=prompt
        )
        return response.output_text.strip().lower()
    
    def send_email(self, to: str, subject: str, body: str, thread_id=None):
        print(f"📤 [DEMO] Sent email to {to}: {subject}")
        msg =  {
            "id": str(uuid.uuid4()),
            "to": to,
            "subject": subject,
            "body": body,
            "threadId": thread_id or str(uuid.uuid4()),
            "date": datetime.utcnow().isoformat(),
            "from": self.from_address,
        }
    
        self.sent.append(msg)
        return msg
    
    def send_email_with_attachments(self, to: str, subject: str, body: str, attachment_data=None, thread_id=None):
        msg = {
            "id": str(uuid.uuid4()),
            "threadId": thread_id or str(uuid.uuid4()),
            "to": to,
            "from": self.from_address,
            "subject": subject,
            "body": body,
            "attachments": attachment_data or [],
            "date": datetime.utcnow().isoformat(),
        }
        self.sent.append(msg)
        return msg
    @property
    def service(self):
        """
        Optional: stub service to avoid crashes when code uses
        gmail_client.service.users().messages()...
        """
        class _Service:
            class _Users:
                class _Messages:
                    def trash(self, userId, id):
                        print(f"[DEMO] trash({id})")
                        return self

                    def modify(self, userId, id, body):
                        print(f"[DEMO] modify({id}, {body})")
                        return self

                    def execute(self):
                        return None

                def messages(self):
                    return self._Messages()

            def users(self):
                return self._Users()

        return _Service()