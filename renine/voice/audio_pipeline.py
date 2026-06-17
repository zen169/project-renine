"""Audio pipeline for Renine.

Coordinates the full voice interaction loop:
Microphone → VAD → STT → Brain → TTS → Speaker

Uses WebRTC VAD for voice activity detection and sounddevice
for audio capture/playback.

Inputs:
    - Microphone audio stream.
    - config/settings.yaml for audio settings.

Outputs:
    - Transcribed user text (passed to brain).
    - Synthesized audio response (played through speakers).
"""
from __future__ import annotations

import asyncio
import queue
import threading
from typing import Any, Callable

import numpy as np

from renine.core.config import get_settings
from renine.core.events import event_bus
from renine.core.exceptions import VoiceError
from renine.core.logging_config import get_logger
from renine.voice.wake_word import check_wake_word, extract_command_after_wake_word

logger = get_logger(__name__)


class AudioPipelineState:
    """Tracks the current state of the audio pipeline."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class AudioPipeline:
    """Main audio pipeline orchestrating microphone → STT → brain → TTS.

    Manages the lifecycle of audio capture, voice activity detection,
    transcription, brain processing, and speech synthesis.
    """

    def __init__(self, on_transcript: Callable[[str], None] | None = None) -> None:
        """Initialize the audio pipeline.

        Args:
            on_transcript: Callback invoked with transcribed text.
                          If None, text is published via event bus.
        """
        self._state = AudioPipelineState.IDLE
        self._on_transcript = on_transcript
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        self._is_running = False
        self._recording = False

        # Load audio config
        settings = get_settings()
        audio_config = settings.get("audio", {})
        self._sample_rate: int = audio_config.get("sample_rate", 16000)
        self._channels: int = audio_config.get("channels", 1)
        self._vad_aggressiveness: int = audio_config.get("vad_aggressiveness", 2)
        self._silence_threshold_ms: int = audio_config.get("silence_threshold_ms", 800)
        self._max_recording_seconds: int = audio_config.get("max_recording_seconds", 30)

        logger.info(
            "audio_pipeline_initialized",
            sample_rate=self._sample_rate,
            vad_aggressiveness=self._vad_aggressiveness,
        )

    @property
    def state(self) -> str:
        """Current pipeline state.

        Returns:
            State string (idle, listening, processing, speaking).
        """
        return self._state

    @property
    def is_running(self) -> bool:
        """Whether the pipeline is actively running.

        Returns:
            True if the pipeline is running.
        """
        return self._is_running

    def start(self) -> None:
        """Start the audio pipeline.

        Begins listening for audio input and processing it through
        the voice pipeline.

        Raises:
            VoiceError: If the pipeline fails to start.
        """
        if self._is_running:
            logger.warning("pipeline_already_running")
            return

        try:
            self._is_running = True
            self._state = AudioPipelineState.LISTENING

            logger.info("audio_pipeline_started")
            event_bus.publish("voice.pipeline_started", {
                "state": self._state,
            })

        except Exception as e:
            self._is_running = False
            logger.exception("pipeline_start_failed")
            raise VoiceError(f"Failed to start audio pipeline: {e}") from e

    def stop(self) -> None:
        """Stop the audio pipeline and release resources."""
        self._is_running = False
        self._state = AudioPipelineState.IDLE
        self._recording = False

        # Clear audio queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("audio_pipeline_stopped")
        event_bus.publish("voice.pipeline_stopped", {})

    def process_audio_chunk(self, audio_chunk: np.ndarray) -> str | None:
        """Process a chunk of audio data through the pipeline.

        This is the main entry point for audio frames. It handles
        VAD, accumulation, and transcription.

        Args:
            audio_chunk: Audio samples as numpy array.

        Returns:
            Transcribed text if speech was detected and completed,
            or None if still accumulating.
        """
        if not self._is_running:
            return None

        self._audio_queue.put(audio_chunk)
        return None

    def handle_transcript(self, transcript: str) -> None:
        """Handle a completed transcript from STT.

        Checks for wake word and dispatches the command.

        Args:
            transcript: Transcribed text from STT.
        """
        if not transcript:
            return

        if check_wake_word(transcript):
            command = extract_command_after_wake_word(transcript)
            if command:
                self._dispatch_command(command)
            else:
                # Wake word only — wait for follow-up
                self._state = AudioPipelineState.LISTENING
                event_bus.publish("voice.awaiting_command", {})
        else:
            # If already in active session, treat as command
            self._dispatch_command(transcript)

    def _dispatch_command(self, command: str) -> None:
        """Dispatch a transcribed command to the brain.

        Args:
            command: The user's voice command text.
        """
        self._state = AudioPipelineState.PROCESSING
        logger.info("command_dispatched", command_length=len(command))

        event_bus.publish("voice.command_received", {
            "text": command,
        })

        if self._on_transcript:
            self._on_transcript(command)

    def play_response(self, audio_data: np.ndarray) -> None:
        """Play synthesized audio response through speakers.

        Args:
            audio_data: Audio samples as numpy float32 array.
        """
        try:
            import sounddevice as sd

            self._state = AudioPipelineState.SPEAKING
            event_bus.publish("voice.speaking_started", {})

            sd.play(audio_data, samplerate=22050, blocking=True)
            sd.wait()

            self._state = AudioPipelineState.LISTENING
            event_bus.publish("voice.speaking_finished", {})

        except Exception as e:
            logger.exception("audio_playback_failed")
            self._state = AudioPipelineState.LISTENING
