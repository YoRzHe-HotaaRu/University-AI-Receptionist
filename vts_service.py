"""
VTube Studio Service — WebSocket connector + lip sync engine.

Connects to VTubeStudio via WebSocket, creates a 'MouthOpen' custom parameter,
and sends timed mouth movement frames based on audio RMS analysis.

Adapted from example_VTubeStudio_Integrate/ reference code.
"""

import asyncio
import io
import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure VTS logger with its own stderr handler so output
# appears alongside Flask/werkzeug logs (stdout is invisible in some terminals)
logger = logging.getLogger('vts')
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()  # defaults to stderr
    _handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(_handler)

# Optional dependencies — VTS features degrade gracefully if missing
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

logger.info("[VTS] vts_service module loaded")


# =============================================================================
# VTube Studio WebSocket Connector
# =============================================================================

class VTSConnector:
    """WebSocket connector for VTube Studio Plugin API."""

    PLUGIN_NAME = "UITM AI Receptionist"
    PLUGIN_DEVELOPER = "UITM"

    def __init__(self, host: str = "localhost", port: int = 8001):
        self.host = host
        self.port = port
        self.websocket = None
        self.authenticated = False
        self.auth_token = None
        self._request_id = 0
        self._token_path = Path(__file__).parent / ".vts_token"
        self._load_token()

    def _load_token(self):
        if self._token_path.exists():
            try:
                self.auth_token = self._token_path.read_text().strip()
                logger.info("[VTS] Loaded saved auth token")
            except Exception as e:
                logger.warning(f"[VTS] Could not load token: {e}")

    def _save_token(self, token: str):
        try:
            self._token_path.write_text(token)
            logger.info("[VTS] Auth token saved")
        except Exception as e:
            logger.warning(f"[VTS] Could not save token: {e}")

    def _get_request_id(self) -> str:
        self._request_id += 1
        return f"UITM_VTS_{self._request_id}"

    async def _send_request(self, request_type: str, data: Dict = None) -> Dict:
        if not self.websocket:
            raise ConnectionError("Not connected to VTube Studio")

        request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": self._get_request_id(),
            "messageType": request_type,
            "data": data or {}
        }

        await self.websocket.send(json.dumps(request))
        response = await self.websocket.recv()
        return json.loads(response)

    @property
    def is_connected(self) -> bool:
        return self.websocket is not None and self.authenticated

    async def connect(self) -> bool:
        if not WEBSOCKETS_AVAILABLE:
            logger.error("[VTS] websockets library not installed")
            return False

        try:
            uri = f"ws://{self.host}:{self.port}"
            logger.info(f"[VTS] Connecting to {uri}...")
            self.websocket = await websockets.connect(uri)
            logger.info("[VTS] Connected to VTube Studio!")
            return await self._authenticate()

        except ConnectionRefusedError:
            logger.warning("[VTS] VTube Studio is not running or API is disabled")
            return False
        except Exception as e:
            logger.warning(f"[VTS] Connection error: {e}")
            return False

    async def _authenticate(self) -> bool:
        # Try saved token first
        if self.auth_token:
            logger.info("[VTS] Authenticating with saved token...")
            response = await self._send_request("AuthenticationRequest", {
                "pluginName": self.PLUGIN_NAME,
                "pluginDeveloper": self.PLUGIN_DEVELOPER,
                "authenticationToken": self.auth_token
            })

            if response.get("data", {}).get("authenticated"):
                logger.info("[VTS] Authentication successful!")
                self.authenticated = True
                return True
            else:
                logger.info("[VTS] Saved token invalid, requesting new token...")
                self.auth_token = None

        # Request new token
        logger.info("[VTS] Requesting new auth token -- click 'Allow' in VTube Studio!")
        response = await self._send_request("AuthenticationTokenRequest", {
            "pluginName": self.PLUGIN_NAME,
            "pluginDeveloper": self.PLUGIN_DEVELOPER
        })

        token = response.get("data", {}).get("authenticationToken")
        if not token:
            error = response.get("data", {}).get("message", "Unknown error")
            logger.error(f"[VTS] Token request failed: {error}")
            return False

        self.auth_token = token
        self._save_token(token)

        # Authenticate with the new token
        response = await self._send_request("AuthenticationRequest", {
            "pluginName": self.PLUGIN_NAME,
            "pluginDeveloper": self.PLUGIN_DEVELOPER,
            "authenticationToken": self.auth_token
        })

        if response.get("data", {}).get("authenticated"):
            logger.info("[VTS] Authentication successful!")
            self.authenticated = True
            return True
        else:
            logger.error("[VTS] Authentication failed")
            return False

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            self.authenticated = False
            logger.info("[VTS] Disconnected")

    async def create_custom_parameter(self, param_name: str,
                                       min_val: float = 0.0,
                                       max_val: float = 1.0,
                                       default_val: float = 0.0) -> bool:
        if not self.is_connected:
            return False

        try:
            response = await self._send_request("ParameterCreationRequest", {
                "parameterName": param_name,
                "explanation": f"Lip sync parameter for {self.PLUGIN_NAME}",
                "min": min_val,
                "max": max_val,
                "defaultValue": default_val
            })

            if response.get("data", {}).get("parameterName"):
                logger.info(f"[VTS] Custom parameter ready: {param_name}")
                return True

            # Parameter might already exist (errorID 352)
            error_id = response.get("data", {}).get("errorID", 0)
            if error_id == 352:
                logger.info(f"[VTS] Parameter already exists: {param_name}")
                return True

            logger.warning(f"[VTS] Could not create parameter: {response}")
            return False
        except Exception as e:
            logger.error(f"[VTS] Error creating parameter: {e}")
            return False

    async def set_parameter(self, name: str, value: float, weight: float = 1.0) -> bool:
        if not self.is_connected:
            return False

        try:
            await self._send_request("InjectParameterDataRequest", {
                "faceFound": True,
                "mode": "set",
                "parameterValues": [
                    {"id": name, "value": float(value), "weight": weight}
                ]
            })
            return True
        except Exception as e:
            logger.error(f"[VTS] Error setting parameter: {e}")
            return False


# =============================================================================
# Lip Sync Engine
# =============================================================================

class LipSyncEngine:
    """Converts MP3 audio to mouth movement frames for VTS."""

    PARAM_NAME = "MouthOpen"

    def __init__(self,
                 target_fps: int = 30,
                 smoothing: float = 0.3,
                 sensitivity: float = 3.0,
                 min_threshold: float = 0.02):
        self.target_fps = target_fps
        self.smoothing = smoothing
        self.sensitivity = sensitivity
        self.min_threshold = min_threshold

    def analyze_mp3(self, mp3_bytes: bytes) -> List[Tuple[float, float]]:
        """
        Convert MP3 bytes to a list of (timestamp, mouth_value) frames.

        Uses pydub to decode MP3 → raw PCM, then calculates RMS per frame.
        """
        if not PYDUB_AVAILABLE or not NUMPY_AVAILABLE:
            logger.warning("[LipSync] pydub or numpy not installed, skipping analysis")
            return []

        try:
            # Decode MP3 to raw audio
            audio_segment = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
            audio_segment = audio_segment.set_channels(1)  # Mono

            # Convert to numpy array
            samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
            sample_rate = audio_segment.frame_rate

            # Normalize to [-1, 1]
            max_val = np.iinfo(np.int16).max
            samples = samples / max_val

            # Calculate frames
            samples_per_frame = int(sample_rate / self.target_fps)
            num_frames = len(samples) // samples_per_frame

            if num_frames == 0:
                return []

            results = []
            previous = 0.0

            for i in range(num_frames):
                start = i * samples_per_frame
                end = start + samples_per_frame
                chunk = samples[start:end]

                # RMS amplitude
                rms = float(np.sqrt(np.mean(chunk ** 2)))

                # Apply threshold
                if rms < self.min_threshold:
                    value = 0.0
                else:
                    value = min(1.0, rms * self.sensitivity)

                # Smoothing
                value = previous * self.smoothing + value * (1 - self.smoothing)
                previous = value

                timestamp = i / self.target_fps
                results.append((timestamp, value))

            logger.info(f"[LipSync] Analyzed {len(results)} frames "
                        f"({results[-1][0]:.1f}s duration)")
            return results

        except Exception as e:
            logger.error(f"[LipSync] Error analyzing audio: {e}")
            return []


# =============================================================================
# Background VTS Manager
# =============================================================================

class VTSManager:
    """
    Manages the VTS connection and lip sync playback in a background thread.
    Runs its own asyncio event loop so it doesn't block Flask.
    """

    def __init__(self, host: str = "localhost", port: int = 8001,
                 playback_speed: float = 1.05):
        self.host = host
        self.port = port
        self.playback_speed = playback_speed
        self.connector = VTSConnector(host, port)
        self.lip_sync = LipSyncEngine()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._connected = False
        self._stop_event = threading.Event()

    def start(self):
        """Start the background VTS thread and connect."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        """Background thread entry point — runs asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._connect_and_setup())
        except Exception as e:
            logger.error(f"[VTS] Background loop error: {e}")
        finally:
            self._loop.close()

    async def _connect_and_setup(self):
        """Connect to VTS with auto-retry, then create the MouthOpen parameter."""
        retry_interval = 10  # seconds between retries
        
        while not self._stop_event.is_set():
            success = await self.connector.connect()
            if success:
                break
            logger.info(f"[VTS] Will retry connection in {retry_interval}s...")
            # Wait with periodic checks so we can stop quickly
            for _ in range(retry_interval):
                if self._stop_event.is_set():
                    return
                await asyncio.sleep(1)
        
        if self._stop_event.is_set():
            return

        # Create MouthOpen custom parameter
        await self.connector.create_custom_parameter(
            LipSyncEngine.PARAM_NAME, 0.0, 1.0, 0.0
        )
        self._connected = True
        logger.info("[VTS] Ready -- lip sync enabled!")

        # Keep the connection alive until stopped
        while not self._stop_event.is_set():
            await asyncio.sleep(1)

        await self.connector.disconnect()

    @property
    def is_ready(self) -> bool:
        return self._connected and self.connector.is_connected

    def play_lip_sync(self, mp3_bytes: bytes):
        """
        Analyze MP3 and play lip sync frames (fire-and-forget from main thread).
        """
        if not self.is_ready:
            logger.debug("[VTS] Not connected, skipping lip sync")
            return

        frames = self.lip_sync.analyze_mp3(mp3_bytes)
        if not frames:
            return

        # Schedule playback on the background event loop
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._play_frames(frames), self._loop
            )

    async def _play_frames(self, frames: List[Tuple[float, float]]):
        """Send timed mouth movement frames to VTS."""
        start_time = asyncio.get_event_loop().time()

        for timestamp, mouth_value in frames:
            if self._stop_event.is_set():
                break

            # Adjust for playback speed
            adjusted_time = timestamp / self.playback_speed
            current = asyncio.get_event_loop().time() - start_time
            wait = adjusted_time - current

            if wait > 0:
                await asyncio.sleep(wait)

            await self.connector.set_parameter(
                LipSyncEngine.PARAM_NAME, mouth_value
            )

        # Close mouth when done
        await self.connector.set_parameter(LipSyncEngine.PARAM_NAME, 0.0)

    def stop(self):
        """Stop the background thread and disconnect."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self._connected = False


# =============================================================================
# Module-level API
# =============================================================================

_manager: Optional[VTSManager] = None


def init_vts(enabled: bool = True, host: str = "localhost",
             port: int = 8001, playback_speed: float = 1.05):
    """
    Initialize the VTS manager. Call once at app startup.
    """
    global _manager

    logger.info(f"[VTS] init_vts called (enabled={enabled}, host={host}, port={port})")

    if not enabled:
        logger.info("[VTS] VTubeStudio integration disabled (VTS_ENABLED=false)")
        return

    if not WEBSOCKETS_AVAILABLE:
        logger.warning("[VTS] websockets library not installed")
        return

    if not PYDUB_AVAILABLE:
        logger.warning("[VTS] pydub library not installed")
        return

    if not NUMPY_AVAILABLE:
        logger.warning("[VTS] numpy library not installed")
        return

    _manager = VTSManager(host, port, playback_speed)
    _manager.start()
    logger.info(f"[VTS] VTubeStudio integration starting (ws://{host}:{port})")


def vts_lip_sync(mp3_bytes: bytes):
    """
    Fire-and-forget lip sync for the given MP3 audio.
    Safe to call even if VTS is not connected — will silently skip.
    """
    if _manager:
        _manager.play_lip_sync(mp3_bytes)


def shutdown_vts():
    """Clean shutdown of VTS connection."""
    global _manager
    if _manager:
        _manager.stop()
        _manager = None
