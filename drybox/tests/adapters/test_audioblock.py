# drybox/tests/adapters/test_audioblock.py
# Tests for AudioBlock adapter base class

import numpy as np
import pytest
from typing import Dict, Any
import sys
sys.path.insert(0, '.')
from drybox.adapters.audioblock import AudioBlockAdapter, nade_capabilities


class ConcreteAudioAdapter(AudioBlockAdapter):
    """Concrete implementation for testing"""
    
    def __init__(self):
        super().__init__()
        self.timer_calls = 0
        self.tx_calls = 0
        self.rx_blocks = []
    
    def on_timer(self, t_ms: int) -> None:
        self.timer_calls += 1
    
    def pull_tx_block(self, t_ms: int) -> np.ndarray:
        self.tx_calls += 1
        return np.ones(self.BLOCK_SAMPLES, dtype=np.int16) * 100
    
    def push_rx_block(self, pcm: np.ndarray, t_ms: int) -> None:
        self.rx_blocks.append((t_ms, pcm.copy()))


class TestAudioBlockAdapter:
    """Test AudioBlockAdapter base class"""
    
    def test_constants(self):
        """Test class constants"""
        assert AudioBlockAdapter.SAMPLE_RATE == 8000
        assert AudioBlockAdapter.BLOCK_SAMPLES == 160
    
    def test_init(self):
        """Test adapter initialization"""
        adapter = ConcreteAudioAdapter()
        assert adapter.side == "unknown"
        assert adapter.cfg == {}
        assert adapter.ctx is None
    
    def test_init_with_config(self):
        """Test init method with configuration"""
        adapter = ConcreteAudioAdapter()
        cfg = {"side": "L", "mode": "audio", "seed": 42}
        adapter.init(cfg)
        
        assert adapter.cfg == cfg
        assert adapter.side == "L"
    
    def test_start_with_context(self):
        """Test start method with context"""
        adapter = ConcreteAudioAdapter()
        
        # Mock context object
        class MockCtx:
            def __init__(self):
                self.side = "R"
        
        ctx = MockCtx()
        adapter.start(ctx)
        
        assert adapter.ctx is ctx
        assert adapter.side == "R"  # Updated from context
    
    def test_lifecycle(self):
        """Test complete adapter lifecycle"""
        adapter = ConcreteAudioAdapter()
        
        # Init phase
        cfg = {"side": "L", "mode": "audio"}
        adapter.init(cfg)
        assert adapter.side == "L"
        
        # Start phase
        ctx = {"some": "context"}
        adapter.start(ctx)
        assert adapter.ctx == ctx
        
        # Operation phase
        adapter.on_timer(100)
        assert adapter.timer_calls == 1
        
        tx_block = adapter.pull_tx_block(100)
        assert len(tx_block) == 160
        assert tx_block.dtype == np.int16
        assert adapter.tx_calls == 1
        
        rx_block = np.ones(160, dtype=np.int16) * 200
        adapter.push_rx_block(rx_block, 120)
        assert len(adapter.rx_blocks) == 1
        assert adapter.rx_blocks[0][0] == 120
        
        # Stop phase
        adapter.stop()
    
    def test_abstract_methods(self):
        """Test that abstract methods must be implemented"""
        # Can't instantiate abstract class directly
        with pytest.raises(TypeError):
            AudioBlockAdapter()


class TestNadeCapabilities:
    """Test capability discovery function"""
    
    def test_capabilities_structure(self):
        """Test capabilities returns correct structure"""
        caps = nade_capabilities()
        
        assert isinstance(caps, dict)
        assert caps["abi_version"] == "1.0"
        assert caps["bytelink"] == False
        assert caps["audioblock"] == True
        assert "audioparams" in caps
    
    def test_audio_params(self):
        """Test audio parameters in capabilities"""
        caps = nade_capabilities()
        params = caps["audioparams"]
        
        assert params["sr"] == 8000
        assert params["block"] == 160
    
    def test_capabilities_complete(self):
        """Test all required fields are present"""
        caps = nade_capabilities()
        required_fields = ["abi_version", "bytelink", "audioblock", "audioparams"]
        
        for field in required_fields:
            assert field in caps