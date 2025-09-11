# drybox/tests/radio/test_vocoder_models.py
# Tests for vocoder implementations and PLC

import numpy as np
import pytest
from drybox.radio.vocoder_models import (
    VocoderBase, AMR12k2Mock, EVS13k2Mock, OpusNBMock, create_vocoder
)


class TestVocoderBase:
    """Test base vocoder functionality"""
    
    def test_plc_no_previous_frame(self):
        """Test PLC when no previous frame exists"""
        class TestVocoder(VocoderBase):
            def encode(self, pcm): return b"test"
            def decode(self, bitstream): return np.zeros(160, dtype=np.int16)
        
        vocoder = TestVocoder()
        plc_frame = vocoder.process_frame(None)
        
        assert len(plc_frame) == 160
        assert plc_frame.dtype == np.int16
        assert np.all(plc_frame == 0)  # Should be silence
    
    def test_plc_frame_repetition(self):
        """Test PLC repeats last good frame"""
        class TestVocoder(VocoderBase):
            def encode(self, pcm): return b"test"
            def decode(self, bitstream): return pcm
        
        vocoder = TestVocoder()
        
        # Send a good frame
        good_frame = np.ones(160, dtype=np.int16) * 1000
        result = vocoder.process_frame(good_frame)
        np.testing.assert_array_equal(result, good_frame)
        
        # First concealment should repeat
        plc1 = vocoder.process_frame(None)
        np.testing.assert_array_equal(plc1, good_frame)
    
    def test_plc_attenuation(self):
        """Test PLC applies gradual attenuation"""
        class TestVocoder(VocoderBase):
            def encode(self, pcm): return b"test"
            def decode(self, bitstream): return pcm
        
        vocoder = TestVocoder()
        
        # Send a good frame
        good_frame = np.ones(160, dtype=np.int16) * 1000
        vocoder.process_frame(good_frame)
        
        # Test attenuation over consecutive losses
        plc1 = vocoder.process_frame(None)  # First loss - full amplitude
        plc2 = vocoder.process_frame(None)  # Second loss - 80% amplitude
        plc3 = vocoder.process_frame(None)  # Third loss - 60% amplitude
        plc4 = vocoder.process_frame(None)  # Fourth loss - silence
        
        assert np.max(np.abs(plc1)) == 1000  # Full amplitude
        assert np.max(np.abs(plc2)) < 1000   # Attenuated
        assert np.max(np.abs(plc3)) < np.max(np.abs(plc2))  # More attenuated
        assert np.all(plc4 == 0)  # Silence after 60ms


class TestAMR12k2Mock:
    """Test AMR vocoder mock"""
    
    def test_init(self):
        """Test AMR initialization"""
        vocoder = AMR12k2Mock(vad_dtx=True, seed=42)
        assert vocoder.frame_size == 160
        assert vocoder.bitrate == 12200
        assert vocoder.vad_dtx == True
    
    def test_encode_decode(self):
        """Test basic encode/decode"""
        vocoder = AMR12k2Mock()
        signal = np.sin(2 * np.pi * 440 * np.arange(160) / 8000) * 10000
        signal = signal.astype(np.int16)
        
        bitstream = vocoder.encode(signal)
        decoded = vocoder.decode(bitstream)
        
        assert bitstream.startswith(b'AMR')
        assert len(decoded) == 160
        assert decoded.dtype == np.int16
    
    def test_vad_dtx(self):
        """Test VAD/DTX functionality"""
        vocoder = AMR12k2Mock(vad_dtx=True)
        
        # Silence should trigger DTX
        silence = np.zeros(160, dtype=np.int16)
        bitstream = vocoder.encode(silence)
        assert bitstream.startswith(b'DTX')
        
        # Decode should generate comfort noise
        decoded = vocoder.decode(bitstream)
        assert len(decoded) == 160
        assert not np.all(decoded == 0)  # Should have some noise
    
    def test_compression_artifacts(self):
        """Test that compression introduces artifacts"""
        vocoder = AMR12k2Mock()
        signal = np.sin(2 * np.pi * 440 * np.arange(160) / 8000) * 10000
        signal = signal.astype(np.int16)
        
        bitstream = vocoder.encode(signal)
        decoded = vocoder.decode(bitstream)
        
        # Should not be identical due to compression
        assert not np.array_equal(signal, decoded)
        
        # But should be similar
        error = np.mean(np.abs(signal - decoded))
        assert error < 5000  # Reasonable error


class TestEVS13k2Mock:
    """Test EVS vocoder mock"""
    
    def test_better_quality_than_amr(self):
        """Test that EVS has better quality than AMR"""
        signal = np.sin(2 * np.pi * 440 * np.arange(160) / 8000) * 10000
        signal = signal.astype(np.int16)
        
        amr = AMR12k2Mock()
        evs = EVS13k2Mock()
        
        amr_bitstream = amr.encode(signal)
        evs_bitstream = evs.encode(signal)
        
        amr_decoded = amr.decode(amr_bitstream)
        evs_decoded = evs.decode(evs_bitstream)
        
        # EVS should have less error
        amr_error = np.mean(np.abs(signal - amr_decoded))
        evs_error = np.mean(np.abs(signal - evs_decoded))
        
        assert evs_error < amr_error


class TestOpusNBMock:
    """Test Opus vocoder mock"""
    
    def test_highest_quality(self):
        """Test that Opus has highest quality"""
        signal = np.sin(2 * np.pi * 440 * np.arange(160) / 8000) * 10000
        signal = signal.astype(np.int16)
        
        opus = OpusNBMock()
        
        bitstream = opus.encode(signal)
        decoded = opus.decode(bitstream)
        
        # Opus should have minimal error
        error = np.mean(np.abs(signal - decoded))
        assert error < 2000  # Very low error


class TestVocoderFactory:
    """Test vocoder factory function"""
    
    def test_create_vocoder(self):
        """Test factory creates correct vocoder types"""
        amr = create_vocoder("amr12k2_mock", vad_dtx=True, seed=42)
        assert isinstance(amr, AMR12k2Mock)
        assert amr.vad_dtx == True
        
        evs = create_vocoder("evs13k2_mock", vad_dtx=False)
        assert isinstance(evs, EVS13k2Mock)
        assert evs.vad_dtx == False
        
        opus = create_vocoder("opus_nb_mock")
        assert isinstance(opus, OpusNBMock)
    
    def test_unknown_vocoder(self):
        """Test factory raises error for unknown vocoder"""
        with pytest.raises(ValueError, match="Unknown vocoder type"):
            create_vocoder("unknown_vocoder")


class TestIntegrationPLC:
    """Integration tests for PLC with vocoders"""
    
    def test_plc_with_vocoder_processing(self):
        """Test PLC works with encoded/decoded frames"""
        vocoder = AMR12k2Mock()
        signal = np.sin(2 * np.pi * 440 * np.arange(160) / 8000) * 10000
        signal = signal.astype(np.int16)
        
        # Process good frame
        bitstream = vocoder.encode(signal)
        decoded = vocoder.decode(bitstream)
        frame1 = vocoder.process_frame(decoded)
        
        # Simulate packet loss
        frame2 = vocoder.process_frame(None)
        
        # Should get repeated frame (not silence)
        assert np.max(np.abs(frame2)) > 100
        
        # Recovery frame
        frame3 = vocoder.process_frame(decoded)
        np.testing.assert_array_equal(frame3, decoded)