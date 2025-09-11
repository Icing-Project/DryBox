# Audio recording test adapter for testing audio capture
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
import sys
import wave
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '.')
from drybox.adapters.audioblock import AudioBlockAdapter


class AudioRecordingTest(AudioBlockAdapter):
    """Test adapter for recording audio and generating test signals"""
    
    def __init__(self):
        super().__init__()
        # Recording settings
        self.record_dir: str = "test_output"
        self.record_prefix: str = "recording"
        self.recording: bool = True
        self.separate_channels: bool = True
        
        # Test signal generation
        self.signal_type: str = "sine"  # sine, chirp, noise, silence
        self.frequency: float = 1000.0
        self.amplitude: float = 0.3
        self.chirp_start: float = 100.0
        self.chirp_end: float = 4000.0
        self.chirp_duration: float = 1.0
        
        # Internal state
        self.tx_samples_generated: int = 0
        self.rx_samples_received: int = 0
        self.rx_buffer: List[Tuple[int, np.ndarray]] = []
        self.tx_writer: Optional[wave.Wave_write] = None
        self.rx_writer: Optional[wave.Wave_write] = None
        
    def init(self, cfg: Dict[str, Any]):
        """Initialize with configuration"""
        super().init(cfg)
        
        # Recording configuration
        self.record_dir = cfg.get('record_dir', self.record_dir)
        self.record_prefix = cfg.get('record_prefix', self.record_prefix)
        self.recording = cfg.get('recording', self.recording)
        self.separate_channels = cfg.get('separate_channels', self.separate_channels)
        
        # Signal configuration
        self.signal_type = cfg.get('signal_type', self.signal_type)
        self.frequency = cfg.get('frequency', self.frequency)
        self.amplitude = cfg.get('amplitude', self.amplitude)
        self.chirp_start = cfg.get('chirp_start', self.chirp_start)
        self.chirp_end = cfg.get('chirp_end', self.chirp_end)
        self.chirp_duration = cfg.get('chirp_duration', self.chirp_duration)
        
        # Setup recording
        if self.recording:
            self._setup_recording()
            
    def _setup_recording(self):
        """Setup WAV file recording"""
        try:
            # Create output directory
            output_path = Path(self.record_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Generate timestamp for unique filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if self.separate_channels:
                # Separate files for TX and RX
                tx_path = output_path / f"{self.record_prefix}_{self.side}_tx_{timestamp}.wav"
                rx_path = output_path / f"{self.record_prefix}_{self.side}_rx_{timestamp}.wav"
                
                # TX writer
                self.tx_writer = wave.open(str(tx_path), 'wb')
                self.tx_writer.setnchannels(1)
                self.tx_writer.setsampwidth(2)
                self.tx_writer.setframerate(self.SAMPLE_RATE)
                
                # RX writer
                self.rx_writer = wave.open(str(rx_path), 'wb')
                self.rx_writer.setnchannels(1)
                self.rx_writer.setsampwidth(2)
                self.rx_writer.setframerate(self.SAMPLE_RATE)
                
                print(f"[AudioRecordingTest] Recording to {tx_path} and {rx_path}")
                
            else:
                # Single file (interleaved or summed)
                combined_path = output_path / f"{self.record_prefix}_{self.side}_{timestamp}.wav"
                # Implementation would depend on requirements
                print(f"[AudioRecordingTest] Combined recording not implemented")
                
        except Exception as e:
            print(f"[AudioRecordingTest] Error setting up recording: {e}")
            self.recording = False
            
    def on_timer(self, t_ms: int) -> None:
        """Timer callback"""
        # Could log periodic statistics
        if t_ms % 1000 == 0:  # Every second
            if self.ctx and hasattr(self.ctx, 'emit_event'):
                self.ctx.emit_event(
                    typ="recording_stats",
                    payload={
                        "tx_samples": self.tx_samples_generated,
                        "rx_samples": self.rx_samples_received,
                        "rx_buffer_size": len(self.rx_buffer)
                    }
                )
                
    def pull_tx_block(self, t_ms: int) -> np.ndarray:
        """Generate test signal block"""
        # Generate signal based on type
        if self.signal_type == "sine":
            block = self._generate_sine()
        elif self.signal_type == "chirp":
            block = self._generate_chirp()
        elif self.signal_type == "noise":
            block = self._generate_noise()
        elif self.signal_type == "silence":
            block = self._generate_silence()
        else:
            # Default to sine
            block = self._generate_sine()
            
        # Record TX if enabled
        if self.recording and self.tx_writer:
            self.tx_writer.writeframes(block.tobytes())
            
        # Update counter
        self.tx_samples_generated += len(block)
        
        return block
        
    def push_rx_block(self, pcm: np.ndarray, t_ms: int) -> None:
        """Receive and record audio block"""
        # Store in buffer
        self.rx_buffer.append((t_ms, pcm.copy()))
        
        # Record RX if enabled
        if self.recording and self.rx_writer:
            self.rx_writer.writeframes(pcm.tobytes())
            
        # Update counter
        self.rx_samples_received += len(pcm)
        
        # Analyze received audio
        self._analyze_rx_block(pcm, t_ms)
        
    def _generate_sine(self) -> np.ndarray:
        """Generate sine wave block"""
        t_start = self.tx_samples_generated / self.SAMPLE_RATE
        t = np.arange(self.BLOCK_SAMPLES) / self.SAMPLE_RATE + t_start
        
        signal = self.amplitude * np.sin(2 * np.pi * self.frequency * t)
        return (signal * 32767).astype(np.int16)
        
    def _generate_chirp(self) -> np.ndarray:
        """Generate chirp signal block"""
        t_start = self.tx_samples_generated / self.SAMPLE_RATE
        t = np.arange(self.BLOCK_SAMPLES) / self.SAMPLE_RATE + t_start
        
        # Linear frequency sweep
        t_norm = np.minimum(t / self.chirp_duration, 1.0)
        freq = self.chirp_start + (self.chirp_end - self.chirp_start) * t_norm
        
        # Generate chirp
        phase = 2 * np.pi * np.cumsum(freq) / self.SAMPLE_RATE
        signal = self.amplitude * np.sin(phase)
        
        return (signal * 32767).astype(np.int16)
        
    def _generate_noise(self) -> np.ndarray:
        """Generate white noise block"""
        signal = self.amplitude * (2 * np.random.random(self.BLOCK_SAMPLES) - 1)
        return (signal * 32767).astype(np.int16)
        
    def _generate_silence(self) -> np.ndarray:
        """Generate silence block"""
        return np.zeros(self.BLOCK_SAMPLES, dtype=np.int16)
        
    def _analyze_rx_block(self, pcm: np.ndarray, t_ms: int):
        """Analyze received audio block"""
        if self.ctx and hasattr(self.ctx, 'emit_event'):
            # Calculate metrics
            signal = pcm.astype(np.float32) / 32768.0
            
            # RMS level
            rms = np.sqrt(np.mean(signal**2))
            rms_db = 20 * np.log10(max(rms, 1e-10))
            
            # Peak level
            peak = np.max(np.abs(signal))
            peak_db = 20 * np.log10(max(peak, 1e-10))
            
            # Simple FFT for frequency analysis
            fft = np.fft.rfft(signal * np.hanning(len(signal)))
            freqs = np.fft.rfftfreq(len(signal), 1/self.SAMPLE_RATE)
            
            # Find peak frequency
            peak_idx = np.argmax(np.abs(fft[1:]))  # Skip DC
            peak_freq = freqs[peak_idx + 1]
            
            self.ctx.emit_event(
                typ="rx_analysis",
                payload={
                    "rms_db": float(rms_db),
                    "peak_db": float(peak_db),
                    "peak_freq": float(peak_freq),
                    "timestamp_ms": t_ms
                }
            )
            
    def close(self):
        """Close resources"""
        if self.tx_writer:
            self.tx_writer.close()
            print(f"[AudioRecordingTest] TX recording saved: {self.tx_samples_generated} samples")
            
        if self.rx_writer:
            self.rx_writer.close()
            print(f"[AudioRecordingTest] RX recording saved: {self.rx_samples_received} samples")
            
            
# The AudioRecordingTest class already inherits the necessary capabilities
# through AudioBlockAdapter, so no additional registration is needed