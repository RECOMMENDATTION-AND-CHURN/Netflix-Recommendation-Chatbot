"""
DEVELOPED BY FAHUMITHA AFROSE(8208E23ASR019)
"""
import os
import time
from typing import Optional
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def ask_gemini(prompt: str) -> Optional[str]:
    """Sends `prompt` to Gemini, retrying up to 3 times with a 2s pause
    between attempts. Returns the raw text response, or None if all 3
    attempts failed (network error, invalid/missing API key, quota, etc.)
    — callers (extract_preferences) treat None as "Gemini unavailable"."""

    for i in range(3):

        try:

            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=prompt
            )

            return response.text

        except Exception as e:

            print(f"Retry {i+1}: {e}")
            time.sleep(2)

    return None
