import json
import os
import logging
from typing import Dict as TypingDict
from typing import List as TypingList

import pyttsx3
from deepseek import conversational_prompt as deepseek_conversational_prompt
from elevenlabs import play
from elevenlabs.client import ElevenLabs

from core.assistant_config import get_config
from core.ollama import conversational_prompt as ollama_conversational_prompt
from utils.utils import build_file_name_session


class PlainAssistant:
    def __init__(self, logger: logging.Logger, session_id: str):
        self.elevenlabs_client = None
        self.logger = logger
        self.session_id = session_id
        self.conversation_history = []

        # Default to local TTS
        self.voice_type = get_config("base_assistant.voice", default="local")

        # Initialize TTS engine
        self.logger.info("🔊 Initializing local TTS engine")
        self.engine = pyttsx3.init()
        self.engine.setProperty("rate", 150)  # Speed of speech
        self.engine.setProperty("volume", 1.0)  # Volume level

        # Get available voices
        voices = self.engine.getProperty("voices")
        # Try to find a female voice
        for voice in voices:
            if "female" in voice.name.lower():
                self.engine.setProperty("voice", voice.id)
                break

        self.session_file = build_file_name_session(
            "conversation_history.json", self.session_id
        )
        self.logger.info(f"📝 Session file created at {self.session_file}")

        self.load_conversation()

        # Get voice configuration
        self.elevenlabs_voice = get_config("base_assistant.elevenlabs_voice")
        self.brain = get_config("base_assistant.brain")

    def load_conversation(self) -> None:
        """Load existing conversation history if it exists."""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, "r") as file:
                    self.conversation_history = json.load(file)
                self.logger.info(
                    f"📖 Loaded conversation history from {self.session_file}"
                )
        except Exception as e:
            self.logger.error(f"❌ Error loading conversation: {str(e)}")
            self.conversation_history = []

    def save_conversation(self) -> None:
        """Save the conversation history to the session file."""
        try:
            with open(self.session_file, "w") as file:
                json.dump(self.conversation_history, file, indent=2)
            self.logger.info(f"💾 Conversation saved to {self.session_file}")
        except Exception as e:
            self.logger.error(f"❌ Error saving conversation: {str(e)}")

    def process_text(self, text: str) -> str:
        """Process text input and generate response"""
        try:
            # Check if text matches our last response
            if (
                self.conversation_history
                and text.strip().lower()
                in self.conversation_history[-1]["content"].lower()
            ):
                self.logger.info("🤖 Ignoring own speech input")
                return ""

            # Add user message to conversation history
            self.conversation_history.append({"role": "user", "content": text})

            # Generate response using configured brain
            self.logger.info(f"🤖 Processing text with {self.brain}...")
            if self.brain.startswith("ollama:"):
                model_no_prefix = ":".join(self.brain.split(":")[1:])
                response = ollama_conversational_prompt(
                    self.conversation_history, model=model_no_prefix
                )
            else:
                response = deepseek_conversational_prompt(self.conversation_history)

            # Add assistant response to history
            self.conversation_history.append({"role": "assistant", "content": response})

            # Speak the response
            self.speak(response)

            return response

        except Exception as e:
            self.logger.error(f"❌ Error occurred: {str(e)}")
            raise

    def speak(self, text: str):
        """Convert text to speech using configured engine"""
        try:
            self.logger.info(f"🔊 Speaking: {text}")

            if self.voice_type == "local":
                self.engine.say(text)
                self.engine.runAndWait()

            elif self.voice_type == "realtime-tts":
                self.stream.feed(text)
                self.stream.play()

            elif self.voice_type == "elevenlabs":
                audio = self.elevenlabs_client.generate(
                    text=text,
                    voice=self.elevenlabs_voice,
                    model="eleven_turbo_v2",
                    stream=False,
                )
                play(audio)

            self.logger.info(f"🔊 Spoken: {text}")

        except Exception as e:
            self.logger.error(f"❌ Error in speech synthesis: {str(e)}")
            raise

    def process_input(self, text):
        pass
