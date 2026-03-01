"""
Lip Sync Analyzer for VTube Studio
Analyzes audio data to generate mouth movement parameters.
"""

import io
import numpy as np
from typing import List, Tuple, Optional
import scipy.io.wavfile as wavfile


class LipSyncAnalyzer:
    """
    Analyzes audio waveforms to generate lip sync data.
    Converts audio amplitude to mouth open values for Live2D models.
    """
    
    # Parameter name for mouth - this is created as a custom parameter
    PARAM_NAME = "MouthOpen"
    
    def __init__(self, 
                 target_fps: int = 30,
                 smoothing: float = 0.3,
                 sensitivity: float = 3.0,  # Increased for more visible mouth movement
                 min_threshold: float = 0.02):
        """
        Initialize the lip sync analyzer.
        
        Args:
            target_fps: Frame rate for mouth updates (default: 30)
            smoothing: Smoothing factor to reduce jitter (0.0-1.0)
            sensitivity: Amplitude multiplier
            min_threshold: Minimum amplitude to register as mouth movement
        """
        self.target_fps = target_fps
        self.smoothing = smoothing
        self.sensitivity = sensitivity
        self.min_threshold = min_threshold
        self._previous_value = 0.0
        
    def analyze_wav_bytes(self, wav_data: bytes) -> List[Tuple[float, float]]:
        """
        Analyze WAV audio bytes and generate lip sync data.
        
        Args:
            wav_data: WAV file as bytes
            
        Returns:
            List of (timestamp_seconds, mouth_value) tuples
        """
        try:
            # Read WAV data
            wav_buffer = io.BytesIO(wav_data)
            sample_rate, audio = wavfile.read(wav_buffer)
            
            return self.analyze_audio(audio, sample_rate)
            
        except Exception as e:
            print(f"[LipSync] Error analyzing audio: {e}")
            return []
    
    def analyze_audio(self, audio: np.ndarray, sample_rate: int) -> List[Tuple[float, float]]:
        """
        Analyze audio array and generate lip sync data.
        
        Args:
            audio: Audio samples as numpy array
            sample_rate: Audio sample rate in Hz
            
        Returns:
            List of (timestamp_seconds, mouth_value) tuples
        """
        # Convert stereo to mono if needed
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        
        # Normalize audio to float32 in range [-1, 1]
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.int32:
            audio = audio.astype(np.float32) / 2147483648.0
        elif audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        # Calculate samples per frame
        samples_per_frame = int(sample_rate / self.target_fps)
        num_frames = len(audio) // samples_per_frame
        
        if num_frames == 0:
            return []
        
        results = []
        previous = 0.0
        
        for i in range(num_frames):
            start = i * samples_per_frame
            end = start + samples_per_frame
            chunk = audio[start:end]
            
            # Calculate RMS amplitude
            rms = np.sqrt(np.mean(chunk ** 2))
            
            # Apply threshold
            if rms < self.min_threshold:
                value = 0.0
            else:
                # Normalize and apply sensitivity
                value = min(1.0, rms * self.sensitivity)
            
            # Apply smoothing
            value = previous * self.smoothing + value * (1 - self.smoothing)
            previous = value
            
            # Calculate timestamp
            timestamp = i / self.target_fps
            
            results.append((timestamp, value))
        
        return results
    
    def get_mouth_parameters(self, mouth_value: float) -> List[dict]:
        """
        Convert mouth value to VTS parameter format.
        
        Args:
            mouth_value: Mouth open value (0.0 to 1.0)
            
        Returns:
            List of parameter dicts for VTS
        """
        # Convert numpy float32 to native Python float for JSON serialization
        value = float(mouth_value)
        return [{"id": self.PARAM_NAME, "value": value, "weight": 1.0}]
    
    def reset(self):
        """Reset the analyzer state (smoothing memory)."""
        self._previous_value = 0.0


class LipSyncPlayer:
    """
    Plays back lip sync data by sending timed parameter updates.
    Coordinates with audio playback for synchronized mouth movement.
    """
    
    def __init__(self, analyzer: Optional[LipSyncAnalyzer] = None):
        """
        Initialize the lip sync player.
        
        Args:
            analyzer: LipSyncAnalyzer instance (creates default if None)
        """
        self.analyzer = analyzer or LipSyncAnalyzer()
        self._current_playback = None
        self._stop_flag = False
        
    async def play_lip_sync(self, vts_connector, lip_sync_data: List[Tuple[float, float]], 
                            playback_speed: float = 1.3):
        """
        Play lip sync data with proper timing.
        
        Args:
            vts_connector: VTSConnector instance
            lip_sync_data: List of (timestamp, mouth_value) from analyzer
            playback_speed: Audio playback speed multiplier (default 1.3 to match TTS)
        """
        import asyncio
        
        if not lip_sync_data:
            return
            
        self._stop_flag = False
        start_time = asyncio.get_event_loop().time()
        
        for timestamp, mouth_value in lip_sync_data:
            if self._stop_flag:
                break
            
            # Adjust timestamp for playback speed
            adjusted_timestamp = timestamp / playback_speed
                
            # Wait until it's time to send this frame
            current_time = asyncio.get_event_loop().time() - start_time
            wait_time = adjusted_timestamp - current_time
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            # Send mouth parameter
            params = self.analyzer.get_mouth_parameters(mouth_value)
            await vts_connector.set_parameters(params)
        
        # Close mouth when done
        params = self.analyzer.get_mouth_parameters(0.0)
        await vts_connector.set_parameters(params)
    
    def stop(self):
        """Stop current lip sync playback."""
        self._stop_flag = True


# Global instances
_analyzer: Optional[LipSyncAnalyzer] = None
_player: Optional[LipSyncPlayer] = None


def get_analyzer() -> LipSyncAnalyzer:
    """Get or create the global lip sync analyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = LipSyncAnalyzer()
    return _analyzer


def get_player() -> LipSyncPlayer:
    """Get or create the global lip sync player."""
    global _player
    if _player is None:
        _player = LipSyncPlayer(get_analyzer())
    return _player
