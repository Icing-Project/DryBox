# drybox/radio/channel_awgn.py
# Additive White Gaussian Noise (AWGN) channel model

import numpy as np
from typing import Optional


class AWGNChannel:
    """
    Additive White Gaussian Noise channel model.
    Adds Gaussian noise to achieve a specified SNR.
    """
    
    def __init__(self, snr_db: float, seed: Optional[int] = None):
        """
        Initialize AWGN channel.
        
        Args:
            snr_db: Signal-to-Noise Ratio in dB
            seed: Random seed for reproducibility
        """
        self.snr_db = snr_db
        self.rng = np.random.RandomState(seed)
        
    def apply(self, signal: np.ndarray) -> np.ndarray:
        """
        Apply AWGN to the signal.
        
        Args:
            signal: Input signal (int16 PCM)
            
        Returns:
            Noisy signal (int16 PCM)
        """
        if len(signal) == 0:
            return signal.copy()
            
        # Convert to float for processing
        sig_float = signal.astype(np.float32) / 32768.0
        
        # Calculate signal power
        sig_power = np.mean(sig_float ** 2)
        
        # Avoid division by zero
        if sig_power == 0:
            return signal.copy()
        
        # Calculate noise power from SNR
        snr_linear = 10 ** (self.snr_db / 10.0)
        noise_power = sig_power / snr_linear
        
        # Generate AWGN
        noise = self.rng.normal(0, np.sqrt(noise_power), len(sig_float))
        
        # Add noise to signal
        noisy_signal = sig_float + noise
        
        # Clip and convert back to int16
        noisy_signal = np.clip(noisy_signal, -1.0, 1.0)
        return (noisy_signal * 32767).astype(np.int16)
    
    def get_estimated_snr(self, original: np.ndarray, noisy: np.ndarray) -> float:
        """
        Estimate the actual SNR between original and noisy signals.
        
        Args:
            original: Original signal
            noisy: Noisy signal
            
        Returns:
            Estimated SNR in dB
        """
        if len(original) == 0 or len(noisy) == 0:
            return float('inf')
            
        # Convert to float
        orig_float = original.astype(np.float32) / 32768.0
        noisy_float = noisy.astype(np.float32) / 32768.0
        
        # Calculate noise
        noise = noisy_float - orig_float
        
        # Calculate powers
        sig_power = np.mean(orig_float ** 2)
        noise_power = np.mean(noise ** 2)
        
        if noise_power == 0:
            return float('inf')
            
        # Calculate SNR
        snr_linear = sig_power / noise_power
        return 10 * np.log10(snr_linear)