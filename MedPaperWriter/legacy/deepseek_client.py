
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class DeepSeekClient:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )
    
    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 4000) -&gt; str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一位专业的医学论文写作助手，擅长撰写高质量的SCI论文。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"DeepSeek API调用错误: {e}")
            return ""

