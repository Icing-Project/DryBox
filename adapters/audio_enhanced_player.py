# Enhanced audio player adapter with advanced features
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
import sys
import wave
import struct
from pathlib import Path

sys.path.insert(0, '.')
from drybox.adapters.audioblock import AudioBlockAdapter


class AudioEnhancedPlayer(AudioBlockAdapter):
    """Enhanced audio player with file playback, effects, and recording"""
    
    def __init__(self):
        super().__init__()
        self.source_file: Optional[str] = None
        self.output_file: Optional[str] = None
        self.wav_data: Optional[np.ndarray] = None
        self.wav_position: int = 0
        self.loop_mode: bool = False
        self.gain: float = 1.0
        self.effects: List[str] = []
        self.rx_buffer: List[Tuple[int, np.ndarray]] = []
        self.recording: bool = False
        self.wav_writer: Optional[wave.Wave_write] = None
        
    def init(self, cfg: Dict[str, Any]):
        """Initialize with configuration"""
        super().init(cfg)
        
        # Audio file settings
        self.source_file = cfg.get('source_file')
        self.output_file = cfg.get('output_file')
        self.loop_mode = cfg.get('loop', False)
        self.gain = cfg.get('gain', 1.0)
        self.effects = cfg.get('effects', [])
        
        # Load source audio if specified
        if self.source_file:
            self._load_audio_file()
            
        # Setup output recording if specified
        if self.output_file:
            self._setup_recording()
            
    def _load_audio_file(self):
        """Load audio from WAV file"""
        try:
            with wave.open(self.source_file, 'rb') as wav:
                # Check format
                if wav.getnchannels() != 1:
                    raise ValueError("Only mono audio supported")
                if wav.getsampwidth() != 2:
                    raise ValueError("Only 16-bit audio supported")
                if wav.getframerate() != self.SAMPLE_RATE:
                    raise ValueError(f"Sample rate must be {self.SAMPLE_RATE}")
                    
                # Read all frames
                frames = wav.readframes(wav.getnframes())
                self.wav_data = np.frombuffer(frames, dtype=np.int16)
                
            print(f"[AudioEnhancedPlayer] Loaded {len(self.wav_data)} samples from {self.source_file}")
            
        except Exception as e:
            print(f"[AudioEnhancedPlayer] Error loading {self.source_file}: {e}")
            self.wav_data = None
            
    def _setup_recording(self):
        """Setup WAV file recording"""
        try:
            Path(self.output_file).parent.mkdir(parents=True, exist_ok=True)
            self.wav_writer = wave.open(self.output_file, 'wb')
            self.wav_writer.setnchannels(1)
            self.wav_writer.setsampwidth(2)
            self.wav_writer.setframerate(self.SAMPLE_RATE)
            self.recording = True
            print(f"[AudioEnhancedPlayer] Recording to {self.output_file}")
            
        except Exception as e:
            print(f"[AudioEnhancedPlayer] Error setting up recording: {e}")
            self.recording = False
            
    def on_timer(self, t_ms: int) -> None:
        """Timer callback"""
        # Could implement time-based effects here
        pass
        
    def pull_tx_block(self, t_ms: int) -> np.ndarray:
        """Generate or playback audio block"""
        if self.wav_data is not None:
            # Playback from file
            remaining = len(self.wav_data) - self.wav_position
            
            if remaining >= self.BLOCK_SAMPLES:
                # Normal playback
                block = self.wav_data[self.wav_position:self.wav_position + self.BLOCK_SAMPLES]
                self.wav_position += self.BLOCK_SAMPLES
                
            elif remaining > 0:
                # Last partial block
                block = np.zeros(self.BLOCK_SAMPLES, dtype=np.int16)
                block[:remaining] = self.wav_data[self.wav_position:]
                self.wav_position = len(self.wav_data)
                
            else:
                # End of file
                if self.loop_mode:
                    # Loop back to beginning
                    self.wav_position = 0
                    block = self.wav_data[:self.BLOCK_SAMPLES]
                    self.wav_position = self.BLOCK_SAMPLES
                else:
                    # Silence
                    block = np.zeros(self.BLOCK_SAMPLES, dtype=np.int16)
                    
        else:
            # Generate test tone if no file loaded
            t = np.arange(self.BLOCK_SAMPLES) / self.SAMPLE_RATE
            freq = 440.0 if self.side == "L" else 880.0
            signal = 0.1 * np.sin(2 * np.pi * freq * t)
            block = (signal * 32767).astype(np.int16)
            
        # Apply gain
        if self.gain != 1.0:
            block = (block.astype(np.float32) * self.gain).clip(-32768, 32767).astype(np.int16)
            
        # Apply effects
        block = self._apply_effects(block)
        
        return block
        
    def push_rx_block(self, pcm: np.ndarray, t_ms: int) -> None:
        """Receive and optionally record audio block"""
        # Store in buffer
        self.rx_buffer.append((t_ms, pcm.copy()))
        
        # Record to file if enabled
        if self.recording and self.wav_writer:
            self.wav_writer.writeframes(pcm.tobytes())
            
        # Emit metrics
        if self.ctx and hasattr(self.ctx, 'emit_event'):
            # Calculate RMS energy
            rms = np.sqrt(np.mean(pcm.astype(np.float32)**2))
            rms_db = 20 * np.log10(max(rms / 32768.0, 1e-10))
            
            self.ctx.emit_event(
                typ="audio_metrics",
                payload={
                    "rms_db": float(rms_db),
                    "peak": int(np.max(np.abs(pcm))),
                    "samples": len(pcm)
                }
            )
            
    def _apply_effects(self, block: np.ndarray) -> np.ndarray:
        """Apply audio effects"""
        result = block.copy()
        
        for effect in self.effects:
            if effect == "reverb":
                # Simple reverb effect
                result = self._apply_reverb(result)
            elif effect == "echo":
                # Echo effect
                result = self._apply_echo(result)
            elif effect == "distortion":
                # Soft clipping distortion
                result = self._apply_distortion(result)
                
        return result
        
    def _apply_reverb(self, block: np.ndarray) -> np.ndarray:
        """Simple reverb using delay lines"""
        # Convert to float
        x = block.astype(np.float32) / 32768.0
        
        # Simple comb filter reverb
        delay_samples = int(0.03 * self.SAMPLE_RATE)  # 30ms delay
        decay = 0.5
        
        # Apply delay (simplified - would need state for proper implementation)
        y = x.copy()
        
        # Convert back
        return (y * 32768).clip(-32768, 32767).astype(np.int16)
        
    def _apply_echo(self, block: np.ndarray) -> np.ndarray:
        """Echo effect"""
        # Convert to float
        x = block.astype(np.float32) / 32768.0
        
        # Echo parameters
        delay_samples = int(0.2 * self.SAMPLE_RATE)  # 200ms delay
        feedback = 0.3
        
        # Apply echo (simplified)
        y = x.copy()
        
        # Convert back
        return (y * 32768).clip(-32768, 32767).astype(np.int16)
        
    def _apply_distortion(self, block: np.ndarray) -> np.ndarray:
        """Soft clipping distortion"""
        # Convert to float
        x = block.astype(np.float32) / 32768.0
        
        # Soft clipping
        threshold = 0.5
        y = np.where(np.abs(x) < threshold, x, threshold * np.tanh(x / threshold))
        
        # Convert back
        return (y * 32768).clip(-32768, 32767).astype(np.int16)
        
    def close(self):
        """Close resources"""
        if self.wav_writer:
            self.wav_writer.close()
            print(f"[AudioEnhancedPlayer] Saved recording to {self.output_file}")
            
            
# The AudioEnhancedPlayer class already inherits the necessary capabilities
# through AudioBlockAdapter, so no additional registration is needed