import os
import sys
import json
import asyncio
import logging
import threading
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger("local_jarvis")

# Import dependencies with fallbacks
try:
    import speech_recognition as sr
    import pyttsx3
except ImportError:
    print("Dependencies missing. Please run: pip install speechrecognition pyttsx3 pyaudio")
    # We will still try to run the logic but skip voice if missing
    sr = None
    pyttsx3 = None

# Import our Brain
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from brain import brain
    from actions import execute_action, parse_desktop_command
    from server import extract_wake_command
except ImportError as e:
    print(f"Error importing internal modules: {e}")
    sys.exit(1)

class LocalJarvis:
    def __init__(self):
        self.engine = None
        if pyttsx3:
            try:
                self.engine = pyttsx3.init()
                # Set a nice British-sounding voice if possible
                voices = self.engine.getProperty('voices')
                for voice in voices:
                    if "United Kingdom" in voice.name or "Hazel" in voice.name:
                        self.engine.setProperty('voice', voice.id)
                        break
                self.engine.setProperty('rate', 175) # Moderate speed
            except Exception as e:
                log.error(f"TTS init failed: {e}")

    def speak(self, text):
        print(f"JARVIS: {text}")
        if self.engine:
            self.engine.say(text)
            self.engine.runAndWait()

    def listen(self):
        if not sr:
            return input("User (type command): ")

        r = sr.Recognizer()
        with sr.Microphone() as source:
            print("\nListening...")
            r.pause_threshold = 1
            r.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = r.listen(source, timeout=5, phrase_time_limit=10)
                print("Recognizing...")
                query = r.recognize_google(audio, language='en-in')
                print(f"User said: {query}")
                return query
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                print("Could not understand audio.")
                return None
            except Exception as e:
                print(f"Recognition error: {e}")
                return input("User (type command): ")

    async def process_command(self, command):
        if not command:
            return

        direct_action = None
        wake_command = extract_wake_command(command)
        if wake_command:
            direct_action = parse_desktop_command(wake_command)
        if direct_action:
            result = await execute_action(direct_action)
            confirmation = result.get("confirmation") or "Done."
            self.speak(confirmation)
            return

        # Simple manual shortcuts for "Human Feel" (Step 6)
        command_lower = command.lower()
        if "sad" in command_lower:
            self.speak("I'm sorry to hear that, sir. Is there anything I can do to help?")
            return

        # Use the Brain to think
        self.speak("Thinking...")
        response = await brain.think(command)
        
        # Check for Actions in response (MCU style)
        # We look for [ACTION:TYPE] or similar tags
        import re
        action_match = re.search(r'\[ACTION:(\w+)\]\s*(.*)', response)
        if action_match:
            action = action_match.group(1).lower()
            target = action_match.group(2).strip()
            self.speak(f"Executing {action}...")
            result = await execute_action({"action": action, "target": target})
            if result.get("confirmation"):
                self.speak(result["confirmation"])
            
            # Clean response text
            response = re.sub(r'\[ACTION:.*?\]', '', response).strip()

        if response:
            self.speak(response)

    def run(self):
        self.speak("Systems online, sir. How can I assist you today?")
        
        while True:
            try:
                command = self.listen()
                if command:
                    if "exit" in command.lower() or "quit" in command.lower():
                        self.speak("Shutting down. Goodbye, sir.")
                        break
                    
                    # Run async processing in a way that works with the loop
                    asyncio.run(self.process_command(command))
            except KeyboardInterrupt:
                break
            except Exception as e:
                log.error(f"Loop error: {e}")

if __name__ == "__main__":
    jarvis = LocalJarvis()
    jarvis.run()
