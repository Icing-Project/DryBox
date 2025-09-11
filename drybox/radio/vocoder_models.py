# drybox/radio/vocoder_models.py
# Mock vocoder implementations with PLC (Packet Loss Concealment)

import numpy as np
from typing import Optional, List, Tuple
from abc import ABC, abstractmethod


class VocoderBase(ABC):
    """Base class for vocoder mocks"""
    
    def __init__(self, vad_dtx: bool = False, seed: Optional[int] = None):
        self.vad_dtx = vad_dtx
        self.rng = np.random.RandomState(seed)
        self.plc_buffer: List[np.ndarray] = []
        self.last_good_frame: Optional[np.ndarray] = None
        self.concealment_count = 0
        
    @abstractmethod
    def encode(self, pcm: np.ndarray) -> bytes:
        """Encode PCM to codec bitstream"""
        pass
    
    @abstractmethod
    def decode(self, bitstream: bytes) -> np.ndarray:
        """Decode bitstream to PCM"""
        pass
    
    def apply_plc(self, frame_size: int) -> np.ndarray:
        """
        Apply Packet Loss Concealment.
        Simple implementation: repeat last good frame with decay.
        """
        if self.last_good_frame is None:
            # No previous frame, return silence
            return np.zeros(frame_size, dtype=np.int16)
        
        self.concealment_count += 1
        
        if self.concealment_count <= 1:
            # First concealment: repeat last frame
            return self.last_good_frame.copy()
        elif self.concealment_count <= 3:
            # Gradual attenuation
            attenuation = 1.0 - (self.concealment_count * 0.2)
            return (self.last_good_frame * attenuation).astype(np.int16)
        else:
            # After 60ms, fade to silence
            return np.zeros(frame_size, dtype=np.int16)
    
    def process_frame(self, pcm: Optional[np.ndarray]) -> np.ndarray:
        """Process a frame with PLC if needed"""
        if pcm is None:
            # Frame lost, apply PLC
            frame_size = len(self.last_good_frame) if self.last_good_frame is not None else 160
            return self.apply_plc(frame_size)
        else:
            # Good frame received
            self.last_good_frame = pcm.copy()
            self.concealment_count = 0
            return pcm


class AMR12k2Mock(VocoderBase):
    """
    Mock AMR 12.2 kbps codec.
    Simulates compression artifacts and frame structure.
    """
    
    def __init__(self, vad_dtx: bool = False, seed: Optional[int] = None):
        super().__init__(vad_dtx, seed)
        self.frame_size = 160  # 20ms @ 8kHz
        self.bitrate = 12200
        
    def encode(self, pcm: np.ndarray) -> bytes:
        """Mock AMR encoding"""
        # Simulate compression by slight quantization
        # Ensure values fit in int8 range
        pcm_float = pcm.astype(np.float32) / 32768.0
        compressed = (pcm_float * 127).clip(-128, 127).astype(np.int8)
        
        # Apply VAD/DTX if enabled
        if self.vad_dtx:
            energy = np.mean(pcm.astype(np.float32)**2)
            if energy < 100:  # Silence threshold
                # DTX: send comfort noise parameters
                return b'DTX' + bytes([0] * 8)
        
        # Mock bitstream (31 bytes for 12.2kbps @ 20ms)
        return b'AMR' + compressed.tobytes()
    
    def decode(self, bitstream: bytes) -> np.ndarray:
        """Mock AMR decoding"""
        if bitstream.startswith(b'DTX'):
            # Generate comfort noise
            noise_level = bitstream[3] if len(bitstream) > 3 else 10
            if noise_level == 0:
                # If noise level is 0 from padding, use default
                noise_level = 10
            return self.rng.normal(0, noise_level, self.frame_size).astype(np.int16)
        
        if bitstream.startswith(b'AMR'):
            # Decode compressed data
            compressed = np.frombuffer(bitstream[3:], dtype=np.int8)
            if len(compressed) >= self.frame_size:
                # Decode back to int16 range
                return (compressed[:self.frame_size].astype(np.float32) / 127.0 * 32767).astype(np.int16)
        
        # Invalid frame
        return np.zeros(self.frame_size, dtype=np.int16)


class EVS13k2Mock(VocoderBase):
    """
    Mock EVS 13.2 kbps codec.
    Higher quality than AMR with better frequency response.
    """
    
    def __init__(self, vad_dtx: bool = False, seed: Optional[int] = None):
        super().__init__(vad_dtx, seed)
        self.frame_size = 160  # 20ms @ 8kHz
        self.bitrate = 13200
        
    def encode(self, pcm: np.ndarray) -> bytes:
        """Mock EVS encoding"""
        # Less aggressive compression than AMR - use more bits
        pcm_float = pcm.astype(np.float32) / 32768.0
        # Simulate higher resolution quantization
        compressed = (pcm_float * 200).clip(-128, 127).astype(np.int8)
        
        # Apply VAD/DTX if enabled
        if self.vad_dtx:
            energy = np.mean(pcm.astype(np.float32)**2)
            if energy < 100:  # Silence threshold
                return b'EVD' + bytes([0] * 10)
        
        # Mock bitstream (33 bytes for 13.2kbps @ 20ms)
        return b'EVS' + compressed.tobytes()
    
    def decode(self, bitstream: bytes) -> np.ndarray:
        """Mock EVS decoding"""
        if bitstream.startswith(b'EVD'):
            # DTX: comfort noise
            noise_level = bitstream[3] if len(bitstream) > 3 else 8
            return self.rng.normal(0, noise_level, self.frame_size).astype(np.int16)
        
        if bitstream.startswith(b'EVS'):
            compressed = np.frombuffer(bitstream[3:], dtype=np.int8)
            if len(compressed) >= self.frame_size:
                # Better reconstruction than AMR
                return (compressed[:self.frame_size].astype(np.float32) / 200.0 * 32767).astype(np.int16)
        
        return np.zeros(self.frame_size, dtype=np.int16)


class OpusNBMock(VocoderBase):
    """
    Mock Opus codec in narrowband mode.
    Modern codec with good quality and loss resilience.
    """
    
    def __init__(self, vad_dtx: bool = False, seed: Optional[int] = None):
        super().__init__(vad_dtx, seed)
        self.frame_size = 160  # 20ms @ 8kHz
        self.bitrate = 16000  # Higher bitrate for better quality
        
    def encode(self, pcm: np.ndarray) -> bytes:
        """Mock Opus encoding"""
        # Minimal compression artifacts
        pcm_float = pcm.astype(np.float32) / 32768.0
        compressed = (pcm_float * 127).clip(-128, 127).astype(np.int8)
        
        if self.vad_dtx:
            energy = np.mean(pcm.astype(np.float32)**2)
            if energy < 80:  # More sensitive VAD
                return b'OPD' + bytes([0] * 12)
        
        # Mock bitstream (40 bytes for 16kbps @ 20ms)
        return b'OPS' + compressed.tobytes()
    
    def decode(self, bitstream: bytes) -> np.ndarray:
        """Mock Opus decoding"""
        if bitstream.startswith(b'OPD'):
            # DTX with better comfort noise
            noise_level = bitstream[3] if len(bitstream) > 3 else 5
            cn = self.rng.normal(0, noise_level, self.frame_size)
            # Smooth comfort noise
            return cn.astype(np.int16)
        
        if bitstream.startswith(b'OPS'):
            compressed = np.frombuffer(bitstream[3:], dtype=np.int8)
            if len(compressed) >= self.frame_size:
                # High quality reconstruction
                return (compressed[:self.frame_size].astype(np.float32) / 127.0 * 32767).astype(np.int16)
        
        return np.zeros(self.frame_size, dtype=np.int16)


def create_vocoder(vocoder_type: str, vad_dtx: bool = False, seed: Optional[int] = None) -> VocoderBase:
    """Factory function to create vocoder instances"""
    vocoders = {
        "amr12k2_mock": AMR12k2Mock,
        "evs13k2_mock": EVS13k2Mock, 
        "opus_nb_mock": OpusNBMock
    }
    
    if vocoder_type not in vocoders:
        raise ValueError(f"Unknown vocoder type: {vocoder_type}")
    
    return vocoders[vocoder_type](vad_dtx=vad_dtx, seed=seed)