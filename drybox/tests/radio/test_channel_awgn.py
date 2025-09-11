# drybox/tests/radio/test_channel_awgn.py
# Tests for AWGN channel implementation

import numpy as np
import pytest
from drybox.radio.channel_awgn import AWGNChannel


class TestAWGNChannel:
    """Test AWGN channel functionality"""
    
    def test_init(self):
        """Test channel initialization"""
        channel = AWGNChannel(snr_db=10.0, seed=42)
        assert channel.snr_db == 10.0
        assert channel.rng is not None
    
    def test_deterministic_noise(self):
        """Test that same seed produces same noise"""
        signal = np.ones(160, dtype=np.int16) * 1000
        
        channel1 = AWGNChannel(snr_db=10.0, seed=42)
        channel2 = AWGNChannel(snr_db=10.0, seed=42)
        
        noisy1 = channel1.apply(signal)
        noisy2 = channel2.apply(signal)
        
        np.testing.assert_array_equal(noisy1, noisy2)
    
    def test_different_seeds_different_noise(self):
        """Test that different seeds produce different noise"""
        signal = np.ones(160, dtype=np.int16) * 1000
        
        channel1 = AWGNChannel(snr_db=10.0, seed=42)
        channel2 = AWGNChannel(snr_db=10.0, seed=43)
        
        noisy1 = channel1.apply(signal)
        noisy2 = channel2.apply(signal)
        
        assert not np.array_equal(noisy1, noisy2)
    
    def test_snr_estimation(self):
        """Test SNR estimation accuracy"""
        # Generate a strong signal
        signal = np.ones(1600, dtype=np.int16) * 10000
        
        for target_snr in [0, 10, 20]:
            channel = AWGNChannel(snr_db=target_snr, seed=42)
            noisy = channel.apply(signal)
            
            estimated_snr = channel.get_estimated_snr(signal, noisy)
            # Allow 2 dB tolerance due to finite sample effects
            assert abs(estimated_snr - target_snr) < 2.0
    
    def test_empty_signal(self):
        """Test handling of empty signal"""
        channel = AWGNChannel(snr_db=10.0)
        signal = np.array([], dtype=np.int16)
        noisy = channel.apply(signal)
        
        assert len(noisy) == 0
        assert noisy.dtype == np.int16
    
    def test_zero_signal(self):
        """Test handling of zero signal"""
        channel = AWGNChannel(snr_db=10.0)
        signal = np.zeros(160, dtype=np.int16)
        noisy = channel.apply(signal)
        
        # Should return a copy of the zero signal
        np.testing.assert_array_equal(noisy, signal)
        assert noisy is not signal  # Should be a copy
    
    def test_clipping(self):
        """Test that output is properly clipped to int16 range"""
        channel = AWGNChannel(snr_db=-10.0, seed=42)  # Very low SNR
        signal = np.ones(160, dtype=np.int16) * 32000  # Near maximum
        
        noisy = channel.apply(signal)
        
        assert noisy.dtype == np.int16
        assert np.all(noisy >= -32768)
        assert np.all(noisy <= 32767)
    
    def test_noise_power(self):
        """Test that noise power matches expected SNR"""
        signal = np.ones(10000, dtype=np.int16) * 10000
        channel = AWGNChannel(snr_db=10.0, seed=42)
        
        noisy = channel.apply(signal)
        
        # Extract noise
        noise = noisy.astype(np.float32) - signal.astype(np.float32)
        
        # Calculate powers
        signal_power = np.mean(signal.astype(np.float32) ** 2)
        noise_power = np.mean(noise ** 2)
        
        # Calculate actual SNR
        actual_snr_db = 10 * np.log10(signal_power / noise_power)
        
        # Should be close to target SNR
        assert abs(actual_snr_db - 10.0) < 1.0