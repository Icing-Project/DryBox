# Simple WAV file player adapter
import numpy as np
from typing import Dict, Any, Optional
import sys
import wave
from pathlib import Path

sys.path.insert(0, '.')
from drybox.adapters.audioblock import AudioBlockAdapter


class AudioWavPlayer(AudioBlockAdapter):
    """Simple WAV file player adapter"""
    
    def __init__(self):
        super().__init__()
        self.wav_file: Optional[str] = None
        self.wav_data: Optional[np.ndarray] = None
        self.playback_position: int = 0
        self.loop: bool = False
        self.gain: float = 1.0
        self.output_file: Optional[str] = None
        self.wav_writer: Optional[wave.Wave_write] = None
        
    def init(self, cfg: Dict[str, Any]):
        """Initialize with configuration"""
        super().init(cfg)
        
        # Get configuration
        self.wav_file = cfg.get('file')
        self.loop = cfg.get('loop', False)
        self.gain = cfg.get('gain', 1.0)
        self.output_file = cfg.get('output')
        
        # Load WAV file if specified
        if self.wav_file:
            self._load_wav_file()
            
        # Setup output recording if specified
        if self.output_file:
            self._setup_output()
            
    def _load_wav_file(self):
        """Load WAV file into memory"""
        try:
            wav_path = Path(self.wav_file)
            if not wav_path.exists():
                print(f"[AudioWavPlayer] WAV file not found: {self.wav_file}")
                return
                
            with wave.open(str(wav_path), 'rb') as wav:
                # Validate format
                channels = wav.getnchannels()
                sampwidth = wav.getsampwidth()
                framerate = wav.getframerate()
                nframes = wav.getnframes()
                
                if channels != 1:
                    print(f"[AudioWavPlayer] Warning: {channels} channels, using first channel only")
                    
                if sampwidth != 2:
                    print(f"[AudioWavPlayer] Error: Only 16-bit audio supported, got {sampwidth*8}-bit")
                    return
                    
                if framerate != self.SAMPLE_RATE:
                    print(f"[AudioWavPlayer] Warning: Sample rate {framerate} != {self.SAMPLE_RATE}")
                    
                # Read all frames
                frames = wav.readframes(nframes)
                
                # Convert to numpy array
                if channels == 1:
                    self.wav_data = np.frombuffer(frames, dtype=np.int16)
                else:
                    # Multi-channel: take first channel
                    all_data = np.frombuffer(frames, dtype=np.int16)
                    self.wav_data = all_data[::channels]
                    
                print(f"[AudioWavPlayer] Loaded {len(self.wav_data)} samples from {self.wav_file}")
                
        except Exception as e:
            print(f"[AudioWavPlayer] Error loading WAV file: {e}")
            
    def _setup_output(self):
        """Setup output WAV file"""
        try:
            output_path = Path(self.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.wav_writer = wave.open(str(output_path), 'wb')
            self.wav_writer.setnchannels(1)
            self.wav_writer.setsampwidth(2)
            self.wav_writer.setframerate(self.SAMPLE_RATE)
            
            print(f"[AudioWavPlayer] Recording output to {self.output_file}")
            
        except Exception as e:
            print(f"[AudioWavPlayer] Error setting up output: {e}")
            
    def on_timer(self, t_ms: int) -> None:
        """Timer callback - not used"""
        pass
        
    def pull_tx_block(self, t_ms: int) -> np.ndarray:
        """Pull next audio block for transmission"""
        # If no WAV data, return silence
        if self.wav_data is None:
            return np.zeros(self.BLOCK_SAMPLES, dtype=np.int16)
            
        # Calculate remaining samples
        remaining = len(self.wav_data) - self.playback_position
        
        if remaining >= self.BLOCK_SAMPLES:
            # Normal case: full block available
            block = self.wav_data[self.playback_position:self.playback_position + self.BLOCK_SAMPLES].copy()
            self.playback_position += self.BLOCK_SAMPLES
            
        elif remaining > 0:
            # Partial block at end of file
            block = np.zeros(self.BLOCK_SAMPLES, dtype=np.int16)
            block[:remaining] = self.wav_data[self.playback_position:]
            
            if self.loop:
                # Fill rest with beginning of file
                block[remaining:] = self.wav_data[:self.BLOCK_SAMPLES - remaining]
                self.playback_position = self.BLOCK_SAMPLES - remaining
            else:
                # End of playback
                self.playback_position = len(self.wav_data)
                
        else:
            # Past end of file
            if self.loop:
                # Start from beginning
                self.playback_position = 0
                block = self.wav_data[:self.BLOCK_SAMPLES].copy()
                self.playback_position = self.BLOCK_SAMPLES
            else:
                # Silence
                block = np.zeros(self.BLOCK_SAMPLES, dtype=np.int16)
                
        # Apply gain
        if self.gain != 1.0:
            # Convert to float, apply gain, clip, convert back
            block = (block.astype(np.float32) * self.gain).clip(-32768, 32767).astype(np.int16)
            
        return block
        
    def push_rx_block(self, pcm: np.ndarray, t_ms: int) -> None:
        """Receive audio block"""
        # Save to output file if configured
        if self.wav_writer:
            self.wav_writer.writeframes(pcm.tobytes())
            
        # Emit basic metrics
        if self.ctx and hasattr(self.ctx, 'emit_event'):
            # Calculate simple metrics
            peak = np.max(np.abs(pcm))
            rms = np.sqrt(np.mean(pcm.astype(np.float32)**2))
            
            self.ctx.emit_event(
                typ="audio_rx",
                payload={
                    "peak": int(peak),
                    "rms": float(rms),
                    "samples": len(pcm)
                }
            )
            
    def close(self):
        """Close resources"""
        if self.wav_writer:
            self.wav_writer.close()
            print(f"[AudioWavPlayer] Output saved to {self.output_file}")
            

# The AudioWavPlayer class already inherits the necessary capabilities
# through AudioBlockAdapter, so no additional registration is needed