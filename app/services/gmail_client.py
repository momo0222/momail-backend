from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import base64
import html
import os
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional, List
from email.utils import parseaddr
from app.core.config import settings

client = OpenAI(api_key=settings.openai_api_key)

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    "https://www.googleapis.com/auth/gmail.modify"

    ]

class PotentialReplies(BaseModel):
    casual: str = Field(description="Short, friendly reply")
    professional: str = Field(description="Formal, professional reply")
    detailed: str = Field(description="Thorough, detailed reply")

class GmailClient:
    def __init__(self, credentials_path: str="credentials.json", token_path: str="token.json"):
        """
        Initialize Gmail Client with OAuth Credentials
        
        :param self: Description
        :param credentials_path: path to oauth credentials json
        :type credentials_path: str
        :param token_path: path to save/load auth token
        :type token_path: str

        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open (token_path, 'w') as file:
                file.write(creds.to_json())

        self.service = build("gmail", "v1", credentials=creds)
        self.profile = self.service.users().getProfile(userId="me").execute()
        self.from_address = self.profile["emailAddress"]
        

    def list_messages(self, max_results: int = 10, query: str = '') -> list:
        """
        Returns a list of recent emails, limited by max_results
        
        :param self: Description
        :param max_results: maximum number of emails returned
        :param query: Gmail search query (e.g., 'from:someone@gmail.com')
        :type max_results: int
        :return: a list of max_results emails
        :rtype: list
        """
        results = self.service.users().messages().list(
            userId="me",
            maxResults=max_results,
            q=query
        ).execute()
        return results.get("messages", [])
        
    def get_message(self, message_id: str) -> dict:
        """
        Returns the details of a specific email by its id
        
        :param self: Description
        :param message_id: The unique identifier of the email
        :type message_id: str
        :return: Full message data
        :rtype: dict
        
        """
        return self.service.users().messages().get(
            userId="me",
            id=message_id,
            format='full'
        ).execute()
        
    def parse_message(self, message: dict) -> dict:
        """
        Parses raw message from Gmail API into a structured format
        
        :param self: Description
        :param dict: The raw message data from Gmail API
        :type dict: str
        :return: Parsed message with subject, from, to, date, body, name, raw
        :rtype: dict
        
        """
        headers = message["payload"]["headers"]
        
        parsed = {
            'id': message['id'],
            'threadId': message['threadId'],
            'snippet': html.unescape(message.get('snippet', ''))
        }
        keys = ["subject","from", "to", "date"]
        for header in headers:
            name = header["name"].lower()
            if name in keys:
                if name == "from":
                    name, addr = parseaddr(header["value"])

                    parsed["from"] = addr.lower().strip()     # normalized email
                    parsed["name"] = name.strip()                # optional
                    parsed["from-raw"] = header["value"]  
                else:
                    parsed[name] = header["value"]
        parsed["body"] = self._get_body(message['payload'])

        return parsed
    
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

    def generate_reply_suggestions(self, parsed_email: dict) -> list:
        """
        Generate 3 reply suggestions using OpenAI
        
        :param self: Description
        :param parsed_email: Parsed email dict with subject, from, and snippet
        :type parsed_email: dict
        :return: List of 3 reply suggestions: [casual, professional, detailed]
        :rtype: list
        """
        prompt = f"""Generate three responses for this email with the tones: casual, professional, and detailed
            Subject: {parsed_email['subject']}
            From: {parsed_email['from']}
            Body: {parsed_email['body']}
            
            Return the response in a list
        """
        response = client.responses.parse(
            model="gpt-4o-mini",
            input=prompt,
            text_format=PotentialReplies
        )
        if response.output_parsed:
            return [response.output_parsed.casual, response.output_parsed.professional, response.output_parsed.detailed]
        return []
    
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

    def send_email(self, to: str, subject: str, body: str, thread_id: Optional[str]=None) -> dict:
        message = EmailMessage()
        message['To'] = to
        message['Subject'] = subject
        message.set_content(body)
        if thread_id:
            # These headers tell Gmail this is part of a conversation
            message['In-Reply-To'] = f'<{thread_id}@mail.gmail.com>'
            message['References'] = f'<{thread_id}@mail.gmail.com>'
        encoded_msg = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_msg}

        if thread_id:
            create_message['threadId'] = thread_id
        
        send_message = self.service.users().messages().send(userId='me', body=create_message).execute()
        
        return send_message
    
    def send_email_with_attachments(
        self, 
        to: str, 
        subject: str, 
        body: str,
        attachment_data: List[tuple[str, str]] = [], # [(filepath, original_name)]
        thread_id: Optional[str] = None
    ):
        """Send email with file attachments"""
        from app.services.storage import storage_service
        import mimetypes
        from email import encoders
        from email.mime.base import MIMEBase
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        import base64
        
        message = MIMEMultipart()
        message['To'] = to
        message['Subject'] = subject
        
        # Add body
        msg_text = MIMEText(body, 'plain', 'utf-8')
        message.attach(msg_text)
        
        # Add attachments
        for filepath, original_filename in attachment_data:
            content = storage_service.get_file_content(filepath)
            if not content:
                print(f"⚠️ Warning: Could not read attachment: {filepath}")
                continue
            
            # Guess MIME type
            mime_type, _ = mimetypes.guess_type(original_filename)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            
            main_type, sub_type = mime_type.split('/', 1)
            
            # Create the attachment
            attachment = MIMEBase(main_type, sub_type)
            attachment.set_payload(content)
            encoders.encode_base64(attachment)
            
            # ✅ THE KEY FIX: Properly encode the filename
            from email.utils import encode_rfc2231
            attachment.add_header(
                'Content-Disposition',
                'attachment',
                filename=('utf-8', '', original_filename)
            )
            
            message.attach(attachment)
        
        # Encode and send
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        body_data = {'raw': raw_message}
        if thread_id:
            body_data['threadId'] = thread_id
        
        result = self.service.users().messages().send(
            userId='me',
            body=body_data
        ).execute()
        
        print(f"📧 Email sent: {result.get('id')}")
        return result
    
    def mark_as_read(self, message_id: str):
        self.service.users().messages().modify(
                    userId='me',
                    id=message_id,
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()
        
    def archive(self, message_id: str):
        self.service.users().messages().modify(
                    userId='me',
                    id=message_id,
                    body={'removeLabelIds': ['INBOX']}
                ).execute()

    def _get_body(self, payload: dict) -> str:
        if 'body' in payload and 'data' in payload['body']:
            return self._decode_body(payload['body']['data'])
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    if 'data' in part.get('body', {}):
                        return self._decode_body(part['body']['data'])
            for part in payload['parts']:
                if part.get('mimeType') == 'text/html':
                    if 'data' in part.get('body', {}):
                        return self._decode_body(part['body']['data'])
        return 'Could not extract body'

    def _decode_body(self, body: str) -> str:
        decoded_bytes = base64.urlsafe_b64decode(body)
        text = decoded_bytes.decode('utf-8')
        return text.replace('\r\n', '\n').replace('\r', '\n')
