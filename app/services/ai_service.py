from openai import OpenAI
from pydantic import BaseModel
from typing import Optional, List
from app.schemas.ai import AttachedFile
from app.core.config import settings
import logging

class AIService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
    
    def generate_email(
            self,
            to: str,
            subject: str,
            tone: str,
            instructions: str,
            attached_files: Optional[List[AttachedFile]] = None,
            enable_research: Optional[bool] = None
    ) -> str:
        """ 
        Generate email with additional file/research support
        """
        
        prompt = f"""You are helping draft a professional email.

        Recipient: {to}
        Subject: {subject}
        Tone: {tone}

        Instructions: {instructions}
        """
        if attached_files:
            prompt += "\n\nAttached documents for context: \n"
            for file in attached_files:
                prompt += f"\n ---{file.filename}--- \n{file.content}\n"
        if enable_research:
            prompt += """\n
            IMPORTANT: Before drafting, research the recipient's company, recent news, and relevant industry trends to personalize this
            email. Use web search to find:
                - Company information and recent developments
                - Recipient's role and background (if publicly available)
                - Industry context and pain points
                - Relevant news or events to reference
            Then draft a highly personalized, compelling email that references specific details you discovered
            """
        prompt += f"\n\nPlease draft the email body only. Do NOT include subject line or headers."

        response = self.client.responses.create(
            model="gpt-5-mini-2025-08-07",
            input=prompt
        )

        return response.output_text
    

    
ai_service = AIService()