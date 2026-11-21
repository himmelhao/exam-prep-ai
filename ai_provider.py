"""The ONLY file that talks to an AI service.

The rest of the app calls `generate_json(prompt)` and gets a Python dict/list back.
To switch to Groq or Claude later, add a new `_call_<name>` function here and
change AI_PROVIDER in .env. Nothing else in the app needs to change.
"""

import json
import os
import time

from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

MAX_RETRIES = 5
BASE_WAIT_SECONDS = 5  # wait 5s, 10s, 20s, 40s... between retries


class RateLimitError(Exception):
    """Raised when the free-tier quota is used up, even after retrying."""


class AIError(Exception):
    """Any other problem talking to the AI."""


_gemini_client = None


def _get_gemini_client():
    # Created once and reused, so we don't reconnect on every call.
    global _gemini_client
    if _gemini_client is None:
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your-key-here":
            raise AIError("GEMINI_API_KEY is missing. Copy .env.example to .env and add your key.")
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _call_gemini(prompt: str) -> str:
    """Send one prompt to Gemini in JSON mode and return the raw text.
    Raises RateLimitError on HTTP 429 so the retry loop can handle it."""
    from google.genai import errors, types

    client = _get_gemini_client()
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",  # forces valid JSON output
                temperature=0.4,
            ),
        )
    except errors.APIError as e:
        # 429 = quota hit, 503 = servers overloaded. Both are temporary, so retry.
        if e.code in (429, 503):
            raise RateLimitError(str(e)) from e
        raise AIError(f"Gemini error {e.code}: {e.message}") from e
    return response.text


_PROVIDERS = {
    "gemini": _call_gemini,
}


def generate_json(prompt: str):
    """Ask the AI and return parsed JSON. Retries with backoff on rate limits."""
    call = _PROVIDERS.get(AI_PROVIDER)
    if call is None:
        raise AIError(f"Unknown AI_PROVIDER '{AI_PROVIDER}'. Options: {list(_PROVIDERS)}")

    for attempt in range(MAX_RETRIES):
        try:
            text = call(prompt)
            return json.loads(text)
        except RateLimitError:
            if attempt == MAX_RETRIES - 1:
                raise RateLimitError(
                    "The AI service is busy or the free quota is used up. Wait a minute "
                    "(or until tomorrow for the daily limit) and try again."
                )
            wait = BASE_WAIT_SECONDS * (2**attempt)
            print(f"  AI service busy or rate limited. Waiting {wait}s, then retrying...")
            time.sleep(wait)
        except json.JSONDecodeError as e:
            # Rare in JSON mode, but retry once more rather than crash.
            if attempt == MAX_RETRIES - 1:
                raise AIError(f"AI returned invalid JSON: {e}") from e
