# drybox/radio/channel_fading.py
# Rayleigh fading channel model

import numpy as np
from typing import Optional, Tuple


class RayleighFadingChannel:
    """
    Rayleigh fading channel model.
    Simulates multipath fading effects typical in mobile communications.
    """
    
    def __init__(self, 
                 snr_db: float,
                 fd_hz: float = 50.0,  # Maximum Doppler frequency
                 L: int = 8,  # Number of multipath components
                 sample_rate: int = 8000,
                 seed: Optional[int] = None):
        """
        Initialize Rayleigh fading channel.
        
        Args:
            snr_db: Average SNR in dB
            fd_hz: Maximum Doppler frequency in Hz
            L: Number of multipath components
            sample_rate: Sample rate in Hz
            seed: Random seed for reproducibility
        """
        self.snr_db = snr_db
        self.fd_hz = fd_hz
        self.L = L
        self.sample_rate = sample_rate
        self.rng = np.random.RandomState(seed)
        
        # Initialize fading coefficients
        self.h_real = self.rng.randn(L)
        self.h_imag = self.rng.randn(L)
        
        # Normalize initial channel
        power = np.sqrt(np.sum(self.h_real**2 + self.h_imag**2))
        self.h_real /= power
        self.h_imag /= power
        
        # Time tracker for fading evolution
        self.t = 0
        
    def _update_channel(self, n_samples: int):
        """Update channel coefficients based on Doppler frequency"""
        # Simple Jakes model approximation
        dt = n_samples / self.sample_rate
        self.t += dt
        
        # Update each path with different Doppler shifts
        for i in range(self.L):
            # Random Doppler frequency for each path
            doppler = self.fd_hz * (0.5 + 0.5 * self.rng.rand())
            phase_shift = 2 * np.pi * doppler * dt
            
            # Apply phase rotation
            cos_phi = np.cos(phase_shift)
            sin_phi = np.sin(phase_shift)
            
            h_real_new = self.h_real[i] * cos_phi - self.h_imag[i] * sin_phi
            h_imag_new = self.h_real[i] * sin_phi + self.h_imag[i] * cos_phi
            
            # Add small random walk
            self.h_real[i] = h_real_new + 0.01 * self.rng.randn()
            self.h_imag[i] = h_imag_new + 0.01 * self.rng.randn()
        
        # Renormalize to maintain average power
        power = np.sqrt(np.sum(self.h_real**2 + self.h_imag**2))
        if power > 0:
            self.h_real /= power
            self.h_imag /= power
    
    def apply(self, signal: np.ndarray) -> np.ndarray:
        """
        Apply Rayleigh fading to the signal.
        
        Args:
            signal: Input signal (int16 PCM)
            
        Returns:
            Faded signal (int16 PCM)
        """
        if len(signal) == 0:
            return signal.copy()
            
        # Update channel state
        self._update_channel(len(signal))
        
        # Convert to float for processing
        sig_float = signal.astype(np.float32) / 32768.0
        
        # Calculate channel magnitude (Rayleigh distributed)
        h_magnitude = np.sqrt(self.h_real[0]**2 + self.h_imag[0]**2)
        
        # Apply fading (using only first tap for simplicity)
        faded_signal = sig_float * h_magnitude
        
        # Add AWGN based on SNR
        sig_power = np.mean(sig_float ** 2)
        if sig_power > 0:
            snr_linear = 10 ** (self.snr_db / 10.0)
            noise_power = sig_power / snr_linear
            noise = self.rng.normal(0, np.sqrt(noise_power), len(sig_float))
            faded_signal += noise
        
        # Clip and convert back to int16
        faded_signal = np.clip(faded_signal, -1.0, 1.0)
        return (faded_signal * 32767).astype(np.int16)
    
    def get_channel_state(self) -> Tuple[float, float]:
        """
        Get current channel state.
        
        Returns:
            Tuple of (channel_magnitude, channel_phase_degrees)
        """
        h_magnitude = np.sqrt(self.h_real[0]**2 + self.h_imag[0]**2)
        h_phase = np.arctan2(self.h_imag[0], self.h_real[0]) * 180 / np.pi
        return h_magnitude, h_phase