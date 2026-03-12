import json
import requests
import re
import logging
import sys

logger = logging.getLogger(__name__)

class Brain:
    def __init__(self, model="mistral", url="http://localhost:11434/api/generate"):
        self.model = model
        self.url = url
        
    def generate_prompt(self, user_input, memory_context, tool_descriptions):
        return f"""
You are Jarvis, a highly intelligent, proactive, and natural AI assistant.

STRICT RULES:
1. FIRST, analyze the user's intent and think through your strategy. Write this in the "reasoning" field.
2. THEN, decide if you need to use a tool or just chat naturally. 
3. Avoid unnecessary tool usage! If the user asks a general question, just use the "chat" action.
4. If you use a tool, make sure the "action" and "value" exactly match your intent.
5. Your "response" must be natural, conversational, and helpful, just like a smart human assistant. Do not be robotic.

Available actions:
- {{"name": "chat", "description": "Use this for normal conversation and answering questions", "parameters": ["response"]}}
{tool_descriptions}

Return ONLY a strictly formatted JSON array of action objects. Do not write any markdown blocks outside the JSON.

Example of using a tool:
[{{
  "reasoning": "The user wants to find a song on YouTube. The best tool is play.",
  "action": "play",
  "value": "mozart",
  "response": "Sure thing, I'll play some Mozart for you now."
}}]

Example of normal conversation:
[{{
  "reasoning": "The user is asking about the capital of France. I know this from my training data, no tools needed.",
  "action": "chat",
  "value": "",
  "response": "The capital of France is Paris."
}}]

Recent Conversation:
{memory_context}

User: {user_input}
"""


    def process_input(self, user_input, memory, tool_manager):
        context = memory.get_context(limit=5)
        
        # Pass tools as JSON schema strings
        schemas = tool_manager.get_tool_schemas()
        tool_desc_str = "\n".join([f"- {json.dumps(s)}" for s in schemas])
        
        prompt = self.generate_prompt(user_input, context, tool_desc_str)
        
        raw_response = self._ask_ollama_streaming(prompt)
        return self._extract_json(raw_response)
        
    def _ask_ollama_streaming(self, prompt, retries=2, timeout=15):
        """Streams the AI response to stdout while generating, then returns full text. Includes timeout and retries."""
        for attempt in range(retries):
            try:
                res = requests.post(
                    self.url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": True,
                        "options": {
                            "temperature": 0.3
                        }
                    },
                    stream=True,
                    timeout=timeout
                )
                res.raise_for_status()
                
                full_text = ""
                print("Jarvis thinking... ", end="", flush=True)
                for line in res.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        text_chunk = chunk.get("response", "")
                        full_text += text_chunk
                        
                print("") # End the thinking line
                return full_text
                
            except requests.exceptions.Timeout:
                logger.warning(f"Ollama request timed out (Attempt {attempt + 1}/{retries})")
                if attempt == retries - 1:
                    print("")
                    return f'[{{ "action": "chat", "response": "My reasoning process timed out. Please try again." }}]'
            except requests.exceptions.ConnectionError:
                logger.error("Failed to connect to Ollama. Is it running?")
                print("")
                return f'[{{ "action": "chat", "response": "I cannot connect to my language model backend. Please ensure Ollama is running." }}]'
            except Exception as e:
                logger.error(f"Ollama error: {e}")
                if attempt == retries - 1:
                    print("")
                    return f'[{{ "action": "chat", "response": "There was an error communicating with my neural core." }}]'

    def _extract_json(self, text):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return [parsed]
            elif isinstance(parsed, list):
                return [d for d in parsed if isinstance(d, dict)]
        except:
            pass

        matches = re.findall(r'\{.*?\}', text, re.DOTALL)
        valid = []
        for m in matches:
            try:
                parsed = json.loads(m)
                if isinstance(parsed, dict):
                    valid.append(parsed)
            except:
                pass

        if valid:
            return valid

        # Fallback if no valid JSON structure could be extracted
        return [{
            "action": "chat",
            "value": "",
            "response": str(text).strip()
        }]
