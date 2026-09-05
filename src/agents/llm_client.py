import os
try:
    from google import genai
except ImportError:
    genai = None
from dotenv import load_dotenv

load_dotenv()

_key = os.getenv("GEMINI_API_KEY")
_client = genai.Client(api_key=_key) if (_key and genai) else None


def available():
    return _client is not None


def call(prompt, max_tokens=300):
    if not _client:
        return None
    try:
        res = _client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config={"max_output_tokens": max_tokens, "temperature": 0.3},
        )
        text = res.text
        return text.strip() if text else None
    except Exception as e:
        print(e)
        return None
        