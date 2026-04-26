import os
import logging
import asyncio
import subprocess
import traceback
import google.generativeai as genai
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("jarvis.brain")

class JarvisBrain:
    """
    The Unified Brain of JARVIS. 
    Encapsulates all AI logic, multi-provider fallbacks, and tool execution.
    """
    
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
        self.google_key = os.getenv("GOOGLE_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "mistral")
        
        # Priority list for speed and intelligence
        self.gemini_models = [
            'models/gemini-2.0-flash',
            'models/gemini-2.0-flash-lite',
            'models/gemini-flash-latest',
            'models/gemini-pro-latest'
        ]
        self.repairing = False

    def _default_system_prompt(self) -> str:
        return (
            "You are JARVIS, Nithin's unified assistant. "
            "You are one intelligent assistant, not multiple personalities. "
            "Be clear, capable, concise, and natural."
        )

    async def heal_self(self, error_msg: str, traceback_str: str):
        """Automatically trigger a self-repair task via Claude Code."""
        if self.repairing: return
        self.repairing = True
        log.error(f"AUTO-HEAL TRIGGERED: {error_msg}")
        
        try:
            # We use the existing work_mode/actions to spawn Claude Code
            from actions import open_claude_in_project
            jarvis_dir = os.path.dirname(os.path.abspath(__file__))
            repair_prompt = (
                f"I encountered an internal error: {error_msg}\n\n"
                f"Traceback:\n{traceback_str}\n\n"
                "Please analyze my source code (especially server.py and brain.py), "
                "fix the bug, and ensure I am stable. DO NOT ask questions, just fix it."
            )
            await open_claude_in_project(jarvis_dir, repair_prompt)
            log.info("Self-repair task dispatched to Claude Code.")
        except Exception as e:
            log.error(f"Self-healing failed to launch: {e}")
        finally:
            self.repairing = False

    async def think(self, prompt: str, history: list = None, system_prompt: str = "") -> str:
        """Process a thought at INSTANT speed (non-streaming)."""
        log.info(f"Thinking (provider={self.provider})...")
        if not system_prompt:
            system_prompt = self._default_system_prompt()
        
        # Trim history to last 3 messages for speed
        if history and len(history) > 3:
            history = history[-3:]

        try:
            if self.provider == "groq" and self.groq_key:
                return await self._think_groq(prompt, history, system_prompt)
            if self.provider == "google" and self.google_key:
                return await self._think_google(prompt, history, system_prompt)
            if self.provider == "openrouter" and self.openrouter_key:
                return await self._think_openrouter(prompt, history, system_prompt)
            if self.provider == "anthropic" and self.anthropic_key:
                return await self._think_anthropic(prompt, history, system_prompt)
            if self.provider == "openai" and self.openai_key:
                return await self._think_openai(prompt, history, system_prompt)
            if self.provider == "ollama":
                return await self._think_ollama(prompt, history, system_prompt)
        except Exception as e:
            asyncio.create_task(self.heal_self(str(e), traceback.format_exc()))
            return f"Error: {e}"
        return "Offline."

    async def stream_think(self, prompt: str, history: list = None, system_prompt: str = ""):
        """Stream thoughts chunk by chunk for maximum perceived speed."""
        log.info(f"Stream Thinking (provider={self.provider})...")
        if not system_prompt:
            system_prompt = self._default_system_prompt()
        
        if history and len(history) > 3:
            history = history[-3:]

        try:
            if self.provider == "google" and self.google_key:
                async for chunk in self._stream_think_google(prompt, history, system_prompt):
                    yield chunk
            elif self.provider == "groq" and self.groq_key:
                async for chunk in self._stream_think_openai_style(prompt, history, system_prompt, "https://api.groq.com/openai/v1", self.groq_key, "llama-3.3-70b-versatile"):
                    yield chunk
            else:
                # Fallback to non-streaming if not implemented
                yield await self.think(prompt, history, system_prompt)
        except Exception as e:
            log.error(f"Stream failed: {e}")
            yield "I encountered a processing error, sir."

    async def run_command(self, command: str) -> str:
        """Execute a system command on the user's computer."""
        try:
            log.info(f"Executing system command: {command}")
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            output = result.stdout + result.stderr
            return output if output else "Command executed successfully (no output)."
        except Exception as e:
            return f"Command failed: {e}"

    async def _think_google(self, prompt: str, history: list, system_prompt: str) -> str:
        """Hyper-fast thinking path."""
        try:
            genai.configure(api_key=self.google_key)
            model = genai.GenerativeModel('models/gemini-2.0-flash-lite', system_instruction=system_prompt)
            
            contents = []
            if history:
                for m in history:
                    role = "user" if m["role"] == "user" else "model"
                    contents.append({"role": role, "parts": [m["content"]]})
            contents.append({"role": "user", "parts": [prompt]})
            
            # Direct generation, no tools, minimal tokens for instant speed
            response = await asyncio.wait_for(
                model.generate_content_async(
                    contents,
                    generation_config=genai.types.GenerationConfig(max_output_tokens=300)
                ),
                timeout=10.0 # 10 second safety timeout
            )
            return response.text
        except asyncio.TimeoutError:
            log.error("Google AI timed out.")
            return "I'm sorry, sir, the connection is timed out."
        except Exception as e:
            log.warning(f"Instant path failed: {e}")
            return f"Thinking... (Error: {e})"

    async def _stream_think_google(self, prompt: str, history: list, system_prompt: str):
        try:
            genai.configure(api_key=self.google_key)
            model = genai.GenerativeModel('models/gemini-2.0-flash-lite', system_instruction=system_prompt)
            contents = []
            if history:
                for m in history:
                    role = "user" if m["role"] == "user" else "model"
                    contents.append({"role": role, "parts": [m["content"]]})
            contents.append({"role": "user", "parts": [prompt]})
            
            response = await model.generate_content_async(contents, stream=True)
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            log.error(f"Google stream error: {e}")
            yield "..."

    async def _stream_think_openai_style(self, prompt: str, history: list, system_prompt: str, base_url: str, api_key: str, model_name: str):
        try:
            client = AsyncOpenAI(base_url=base_url, api_key=api_key)
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history[-10:])
            messages.append({"role": "user", "content": prompt})
            
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True,
                max_tokens=500
            )
            async for chunk in response:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            log.error(f"OpenAI-style stream error: {e}")
            yield "..."

    async def _think_anthropic(self, prompt: str, history: list, system_prompt: str) -> str:
        try:
            client = AsyncAnthropic(api_key=self.anthropic_key)
            messages = []
            if history:
                messages = history[-10:] # Keep last 10
            messages.append({"role": "user", "content": prompt})
            
            response = await client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=500,
                system=system_prompt,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            return f"Anthropic Brain Error: {e}"

    async def _think_openai(self, prompt: str, history: list, system_prompt: str) -> str:
        try:
            client = AsyncOpenAI(api_key=self.openai_key)
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history[-10:])
            messages.append({"role": "user", "content": prompt})
            
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"OpenAI Brain Error: {e}"

    async def _think_openrouter(self, prompt: str, history: list, system_prompt: str) -> str:
        try:
            # OpenRouter uses the OpenAI client format
            client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=self.openrouter_key,
            )
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history[-10:])
            messages.append({"role": "user", "content": prompt})
            
            response = await client.chat.completions.create(
                model="google/gemini-2.0-flash-lite-preview-02-05:free", # Fast and Free on OpenRouter
                messages=messages,
                max_tokens=500,
                extra_headers={
                    "HTTP-Referer": "https://github.com/jarvis-assistant",
                    "X-Title": "JARVIS",
                }
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"OpenRouter Brain Error: {e}"

    async def _think_groq(self, prompt: str, history: list, system_prompt: str) -> str:
        try:
            # Groq is the absolute speed king (300+ tokens/sec)
            client = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.groq_key,
            )
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history[-10:])
            messages.append({"role": "user", "content": prompt})
            
            response = await client.chat.completions.create(
                model="llama-3.3-70b-versatile", # High quality, insane speed
                messages=messages,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Groq Brain Error: {e}"

    async def _think_ollama(self, prompt: str, history: list, system_prompt: str) -> str:
        """Local inference using Ollama. Truly free and private."""
        try:
            import httpx
            log.info(f"Ollama thinking with model {self.ollama_model}...")
            async with httpx.AsyncClient() as client:
                messages = [{"role": "system", "content": system_prompt}]
                if history:
                    messages.extend(history[-5:])
                messages.append({"role": "user", "content": prompt})

                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.ollama_model,
                        "messages": messages,
                        "stream": False
                    },
                    timeout=httpx.Timeout(120.0, connect=5.0)
                )
                if response.status_code == 200:
                    return response.json()["message"]["content"]
                if response.status_code == 404:
                    return (
                        f"Ollama is reachable, but the model '{self.ollama_model}' was not found. "
                        f"Run: ollama pull {self.ollama_model}"
                    )

                log.error(f"Ollama error: {response.text}")
                return f"Ollama error ({response.status_code}): {response.text}"
        except httpx.ConnectError:
            log.error(f"Ollama connect failed at {self.ollama_url}")
            return f"Ollama connection failed. Make sure Ollama is running on {self.ollama_url}."
        except httpx.TimeoutException:
            log.error("Ollama request timed out")
            return f"Ollama took too long to respond from {self.ollama_url}. Try a smaller model or wait a bit."
        except Exception as e:
            log.error(f"Ollama failed: {e}")
            return f"Ollama failed: {e}"

# Global brain instance
brain = JarvisBrain()
