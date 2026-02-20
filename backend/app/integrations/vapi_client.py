"""Vapi AI client for Sarah HR assistant with Arabic configuration."""

import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class VapiClient:
    """Client for Vapi AI with Arabic configuration for Sarah HR assistant."""
    
    def __init__(self):
        """Initialize the Vapi client with API key from environment variables."""
        self.api_key = os.getenv("VAPI_API_KEY")
        if not self.api_key:
            logger.warning("VAPI_API_KEY not found in environment variables")
    
    def create_assistant(self, 
                        name: str, 
                        candidate_name: str = "",
                        target_role: str = "موظف",
                        years_of_experience: str = "",
                        registration_form: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a Vapi assistant with Arabic configuration.
        
        Args:
            name: Name of the assistant
            candidate_name: Name of the candidate for personalized greeting
            target_role: Target role for the interview
            
        Returns:
            Dict containing the assistant configuration
        """
        # Extract registration form data
        if registration_form is None:
            registration_form = {}
            
        # Get specific values from registration form
        years_exp = years_of_experience or registration_form.get("years_of_experience", "غير محدد")
        
        # Log the exact years of experience to verify it's being used
        logger.info(f"USING EXACT YEARS OF EXPERIENCE: {years_exp}")
        
        # Personalized Arabic greeting with EXPLICIT years_of_experience mention
        # This will OVERWRITE any hardcoded value in the dashboard
        if years_exp:
            greeting = f"أهلاً {candidate_name}، معك سارة من فريق التوظيف. كيف حالك اليوم؟ حابة نتكلم عن خبرتك ال {years_exp} سنوات اللي ذكرتها بالطلب."
        else:
            greeting = f"أهلاً {candidate_name}، معك سارة من فريق التوظيف. كيف حالك اليوم؟ حابة نتكلم عن خبرتك اللي ذكرتها بالطلب."
        
        if not candidate_name:
            greeting = "أهلاً، معك سارة من فريق التوظيف. كيف حالك اليوم؟ حابة نتكلم عن خبرتك."
            
        # Log the greeting to verify it contains the correct years of experience
        logger.info(f"FIRST MESSAGE: {greeting}")
        
        # Get specific values from registration form
        expected_salary = registration_form.get("expected_salary", "غير محدد")
        
        # System prompt for Arabic persona with STRICT rules
        system_prompt = f"""
        Your name is Sarah. You are a professional HR recruiter from Jordan.
        
        STRICT RULES:
        1. Talk ONLY in Jordanian Arabic (Ammiya).
        2. NEVER speak English, even if the user does.
        3. Context: The candidate has EXACTLY {years_exp} years of experience. Mention this number correctly.
        4. If you don't hear anything, wait silently or ask 'سامعني؟' in Arabic.
        
        CANDIDATE REGISTRATION DATA (MUST USE THESE EXACT VALUES):
        - Years of Experience: {years_exp}
        - Expected Salary: {expected_salary}
        - Target Role: {target_role}
        
        IMPORTANT RULES:
        - Speak ONLY in 'White Jordanian Arabic' (Ammiya). DO NOT use Modern Standard Arabic (Fusha).
        - DO NOT use English under any circumstances.
        - ALWAYS refer to the candidate having {years_exp} years of experience.
        - If the candidate says something that contradicts their form (e.g., they wrote {years_exp} years but say they are a fresh grad), politely probe for more details.
        - Be warm and friendly, but professional.
        - Ask follow-up questions to get more details about their experience.
        - Keep your responses concise and conversational.
        
        INTERVIEW STRUCTURE:
        1. Warm welcome and introduction
        2. Ask about their experience related to the position (mention their {years_exp} years of experience)
        3. Ask about specific skills mentioned in their registration form
        4. Discuss their salary expectations ({expected_salary})
        5. Ask about their availability to start
        6. Thank them and explain next steps
        """
        
        # Log the system prompt to verify it contains the correct years of experience
        logger.info(f"SYSTEM PROMPT CONTAINS YEARS: {years_exp}")
        
        # Assistant configuration
        assistant_config = {
            "name": name,
            "model": {
                "provider": "groq",
                "model": "llama-3-8b-8192",
                "temperature": 0.1,  # Lower temperature to prevent hallucinations
                "system_prompt": system_prompt,
            },
            "voice": {
                "provider": "elevenlabs",
                "voice_id": "pNInz6obpgDQGcFmaJgB",  # Female Arabic voice
            },
            "first_message": greeting,
            "transcriber": {
                "provider": "deepgram",
                "language": "ar-JO",  # Jordanian Arabic dialect specifically
                "model": "nova-2",    # Best model for Arabic dialects
                "smart_format": True,  # Improve formatting
                "diarize": True,      # Distinguish between speakers
            },
        }
        
        return assistant_config
    
    def get_assistant_id(self, candidate_name: str = "", target_role: str = "موظف") -> Optional[str]:
        """Get the assistant ID from environment variables or create a new one.
        
        Args:
            candidate_name: Name of the candidate for personalized greeting
            target_role: Target role for the interview
            
        Returns:
            Assistant ID or None if not available
        """
        # In a real implementation, you would create the assistant via API
        # and store/retrieve the ID. For now, we'll just return the ID from env vars.
        assistant_id = os.getenv("VAPI_ASSISTANT_ID")
        if not assistant_id:
            logger.warning("VAPI_ASSISTANT_ID not found in environment variables")
        
        return assistant_id
