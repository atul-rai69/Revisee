from src.settings import settings
from google import genai

client = genai.Client(api_key=settings.GOOGLE_API_KEY)