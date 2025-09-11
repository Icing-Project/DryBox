# drybox/adapters/audioblock.py
# Mode B AudioBlock adapter interface

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import numpy as np


class AudioBlockAdapter(ABC):
    """Base class for Mode B AudioBlock adapters"""
    
    SAMPLE_RATE = 8000  # 8 kHz
    BLOCK_SAMPLES = 160  # 20ms @ 8kHz
    
    def __init__(self):
        self.cfg = {}
        self.side = "unknown"
        self.ctx: Optional[Dict[str, Any]] = None
    
    def init(self, cfg: Dict[str, Any]) -> None:
        """Initialize with configuration"""
        self.cfg = cfg
        self.side = cfg.get("side", "unknown")
    
    def start(self, ctx: Dict[str, Any]) -> None:
        """Initialize adapter with execution context"""
        self.ctx = ctx
        # Update side from context if available
        if hasattr(ctx, 'side'):
            self.side = ctx.side
    
    def stop(self) -> None:
        """Cleanup when adapter stops"""
        pass
    
    @abstractmethod
    def on_timer(self, t_ms: int) -> None:
        """Called at each tick for internal timers"""
        pass
    
    @abstractmethod
    def pull_tx_block(self, t_ms: int) -> np.ndarray:
        """
        Get PCM block to transmit.
        Must return C-contiguous int16 array of BLOCK_SAMPLES length.
        """
        pass
    
    @abstractmethod  
    def push_rx_block(self, pcm: np.ndarray, t_ms: int) -> None:
        """Receive PCM block from the channel"""
        pass


def nade_capabilities() -> Dict[str, Any]:
    """Capability discovery for Mode B"""
    return {
        "abi_version": "1.0",
        "bytelink": False,
        "audioblock": True,
        "audioparams": {
            "sr": AudioBlockAdapter.SAMPLE_RATE,
            "block": AudioBlockAdapter.BLOCK_SAMPLES
        }
    }