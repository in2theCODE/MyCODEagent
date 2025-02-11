from queue import Queue
import asyncio
import logging
import threading
import time
from typing import Optional, Dict, Any
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from elevenlabs import ElevenLabs
from core.assistant_config import get_config
from core.command_processor import VoiceCommand, VoiceCommandProcessor


class VoiceDetector:
    """Lightweight energy-based voice activity detector"""

    def __init__(self, threshold: float = 0.01):
        self.threshold = threshold
        self.window_size = 1024

    def detect_voice(self, audio_data: np.ndarray) -> bool:
        """Return True if voice activity detected"""
        energy = np.mean(np.abs(audio_data))
        return energy > self.threshold


class VoiceServiceError(Exception):
    """Base exception for voice service errors"""
    pass

class MicrophoneError(VoiceServiceError):
    """Raised when microphone is not available"""
    pass

class ASRError(VoiceServiceError):
    """Raised when ASR service fails"""
    pass

class TTSError(VoiceServiceError):
    """Raised when TTS service fails"""
    pass

class VoiceCommandSystem:
    def __init__(self, logger: logging.Logger, model_size: str = "base", run_in_background: bool = True):
        self.logger = logger
        
        try:
            # Initialize components
            self._setup_audio()
            self.voice_detector = VoiceDetector()
            self.asr_model = WhisperModel(model_size)
            self.elevenlabs_client = None
            self.command_processor = VoiceCommandProcessor()
        except Exception as e:
            self.logger.error(f"Failed to initialize voice system: {str(e)}")
            raise

        # State management
        self.is_active = False  # Full system active
        self.is_listening = False  # Actually processing commands
        self.standby_mode = True  # Lightweight detection only

        # Audio processing
        self.sample_rate = 16000
        self.audio_queue = Queue()
        self.standby_buffer = []
        self.buffer_threshold = 48000  # 3 seconds at 16kHz

        # Threading
        self.processing_thread = None
        self.should_run = False

        # Wake word
        self.wake_word = get_config("typer_assistant.wake_word", "hey aiden").lower()

        # Setup TTS
        self.setup_tts()

    def setup_tts(self):
        """Initialize text-to-speech"""
        try:
            api_key = get_config("typer_assistant.elevenlabs_api_key")
            if api_key:
                self.elevenlabs_client = ElevenLabs(api_key=api_key)
                self.logger.info("✅ ElevenLabs TTS initialized")
        except Exception as e:
            self.logger.error(f"❌ Error setting up TTS: {str(e)}")

    async def _audio_callback(self, indata: np.ndarray, frames: int, time, status):
        """Process incoming audio data"""
        if status:
            self.logger.warning(f"Audio callback status: {status}")
            return

        try:
            # Always do lightweight voice detection
            if self.voice_detector.detect_voice(indata):
                if self.standby_mode:
                    # In standby, only buffer when voice detected
                    self.standby_buffer.extend(indata.flatten())

                    # Check buffer size
                    if len(self.standby_buffer) >= self.buffer_threshold:
                        # Process buffer for wake word
                        self._check_wake_word(np.array(self.standby_buffer))
                        self.standby_buffer = []

                elif self.is_listening:
                    # Active listening mode - queue all voice data
                    self.audio_queue.put(indata.copy())

            elif not self.standby_mode and not self.voice_detector.detect_voice(indata):
                # No voice detected for a while when active
                self._consider_standby()

        except Exception as e:
            self.logger.error(f"Error in audio callback: {str(e)}")

    async def _check_wake_word(self, audio_data: np.ndarray):
        """Check audio for wake word using enhanced detection"""
        try:
            # Multi-stage wake word detection
            
            # 1. Quick energy check
            if not self.voice_detector.detect_voice(audio_data, threshold=0.02):
                return False
                
            # 2. VAD check with higher threshold
            if not self.voice_detector.detect_voice(audio_data, threshold=0.05):
                return False
                
            # 3. ASR with Whisper
            segments, info = self.asr_model.transcribe(audio_data)
            text = " ".join(segment.text for segment in segments).lower()
            
            # 4. Enhanced wake word matching
            wake_words = [
                self.wake_word,
                "hey aiden",
                "hi aiden",
                "okay aiden",
                "hey assistant",
                "hello aiden"
            ]
            
            # Use fuzzy matching with confidence threshold
            from difflib import SequenceMatcher
            for wake_word in wake_words:
                matches = [
                    SequenceMatcher(None, wake_word, part).ratio()
                    for part in text.split()
                ]
                if any(score > 0.85 for score in matches):  # Higher confidence threshold
                    self.logger.info(f"Wake word detected with confidence {max(matches):.2f}")
                    await self._activate_system()
                    return True
                
            return False

        except Exception as e:
            self.logger.error(f"Error checking wake word: {str(e)}")
            return False

    async def _background_processing(self):
        """Continuous background processing loop"""
        try:
            while self.should_run:
                if not self.audio_queue.empty():
                    audio_data = self.audio_queue.get()
                    
                    if self.standby_mode:
                        # Only check for wake word when in standby
                        await self._check_wake_word(audio_data)
                    else:
                        # Process commands when active
                        segments, _ = self.asr_model.transcribe(audio_data)
                        for segment in segments:
                            text = segment.text.lower()
                            if "stop listening" in text or "goodbye" in text:
                                await self._enter_standby()
                            else:
                                await self._handle_command(text)
                                
                await asyncio.sleep(0.01)  # Small sleep to prevent CPU overuse
                
        except asyncio.CancelledError:
            self.logger.info("Background processing stopped")
        except Exception as e:
            self.logger.error(f"Error in background processing: {str(e)}")
            
    async def _activate_system(self):
        """Activate the full system"""
        try:
            self.standby_mode = False
            self.is_listening = True
            self.consecutive_silence = 0
            await self.speak("I'm listening")
            self.logger.info("System activated")
            
            # Clear any stale audio data
            while not self.audio_queue.empty():
                self.audio_queue.get()
                
        except Exception as e:
            self.logger.error(f"Error activating system: {str(e)}")
            self.standby_mode = True
            self.is_listening = False

    def _consider_standby(self):
        """Consider returning to standby mode"""
        if not self.voice_detector.detect_voice(np.array([])):
            self.consecutive_silence += 1
            if self.consecutive_silence > 50:  # About 5 seconds
                self._enter_standby()
        else:
            self.consecutive_silence = 0

    def _enter_standby(self):
        """Enter standby mode"""
        self.standby_mode = True
        self.is_listening = False
        self.speak("Entering standby mode")
        self.logger.info("Entered standby mode")

    def _process_commands(self):
        """Process audio commands in separate thread"""
        while self.should_run:
            if not self.audio_queue.empty() and self.is_listening:
                try:
                    audio_data = self.audio_queue.get()
                    segments, _ = self.asr_model.transcribe(audio_data)

                    for segment in segments:
                        text = segment.text.lower()
                        if "stop listening" in text or "goodbye" in text:
                            self._enter_standby()
                        else:
                            self._handle_command(text)

                except Exception as e:
                    self.logger.error(f"Error processing command: {str(e)}")

            time.sleep(0.1)  # Prevent busy waiting

    def _setup_audio(self):
        """Setup audio input with error handling"""
        try:
            devices = sd.query_devices()
            if not any(d['max_input_channels'] > 0 for d in devices):
                raise MicrophoneError("No input devices found")
            # Configure default input device
            input_device = next(d for d in devices if d['max_input_channels'] > 0)
            sd.default.device = input_device['index'], None
        except Exception as e:
            raise MicrophoneError(f"Failed to initialize audio: {str(e)}")

    async def process_command(self, text: str) -> Optional[str]:
        """Process voice command with error recovery"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # First check for wake word
                if not any(wake_word in text.lower() for wake_word in [self.wake_word]):
                    return None

                # Find matching command with history context
                command = self.command_processor.find_matching_command(text)
                if command:
                    result = await self._execute_command(command, text)
                    if result:
                        # Log successful command
                        self.logger.info(f"Successfully executed command: {command.name}")
                        return result
                
                # If we get here, command failed but didn't raise exception
                retry_count += 1
                if retry_count < max_retries:
                    self.logger.warning(f"Retrying command (attempt {retry_count + 1}/{max_retries})")
                    await asyncio.sleep(1)  # Brief delay between retries
                    continue
                
                return "I'm having trouble executing that command. Please try again."

            except Exception as e:
                self.logger.error(f"Error processing command (attempt {retry_count + 1}): {str(e)}")
                retry_count += 1
                if retry_count >= max_retries:
                    return f"I encountered an error and couldn't recover: {str(e)}"
                await asyncio.sleep(1)  # Brief delay between retries

    async def _execute_command(self, command: VoiceCommand, text: str) -> str:
        """Execute a matched command"""
        try:
            params = self._extract_parameters(command, text)
            
            if not all(self.command_processor.validate_parameter(p, params.get(p.name, '')) 
                      for p in command.parameters):
                return f"I couldn't understand all the parameters for {command.name}"

            if command.confirmation_required:
                if not await self._get_confirmation(command, params):
                    return "Command cancelled"

            self.logger.info(f"Executing command: {command.name} with params: {params}")
            return f"Executing {command.name}"

        except Exception as e:
            self.logger.error(f"Error executing command {command.name}: {str(e)}")
            return f"Error executing command: {str(e)}"

    def _extract_parameters(self, command: VoiceCommand, text: str) -> dict:
        """Extract command parameters from voice input"""
        params = {}
        for param in command.parameters:
            # Simple parameter extraction - could be improved with NLP
            if param.name in text.lower():
                words = text.lower().split()
                idx = words.index(param.name)
                if idx + 1 < len(words):
                    params[param.name] = words[idx + 1]
        return params

    async def _get_confirmation(self, command: VoiceCommand, params: dict) -> bool:
        """Get user confirmation for command execution"""
        prompt = command.confirmation_prompt.format(**params) if command.confirmation_prompt else f"Should I execute {command.name}?"
        self.speak(prompt)
        response = await self._wait_for_response()
        return any(word in response.lower() for word in ["yes", "yeah", "sure", "okay"])

    async def start(self):
        """Start the voice command system as a background service"""
        try:
            self.logger.info("Starting voice command system in background...")
            self.should_run = True

            # Start background processing task
            self.processing_task = asyncio.create_task(self._background_processing())

            # Start audio stream
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype=np.float32,
                callback=self._audio_callback,
                blocksize=1024,  # Smaller blocks for faster response
                latency='low'
            )
            
            self.stream.start()
            self.logger.info("🎤 Listening for wake word in background...")
            
            # Keep service running
            while self.should_run:
                await asyncio.sleep(0.1)  # Reduced sleep time for better responsiveness

        except Exception as e:
            self.logger.error(f"Error in voice system: {str(e)}")
            await self.stop()

    async def stop(self):
        """Stop the voice command system"""
        self.should_run = False
        
        # Cancel background task
        if hasattr(self, 'processing_task'):
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
            
        # Stop audio stream
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
            
        self.logger.info("Voice command system stopped")

    def speak(self, text: str):
        """Text-to-speech output"""
        try:
            if self.elevenlabs_client:
                voice = get_config("typer_assistant.elevenlabs_voice")
                audio = self.elevenlabs_client.generate(
                    text=text,
                    voice=voice,
                    model="eleven_turbo_v2"
                )
                self.elevenlabs_client.play(audio)
            else:
                print(text)  # Fallback to print
        except Exception as e:
            self.logger.error(f"Error in speech synthesis: {str(e)}")
            print(text)  # Fallback to print
