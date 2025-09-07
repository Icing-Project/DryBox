#!/bin/bash
# Test script for all implemented Mode B audio features

echo "=== DryBox Mode B Audio Feature Tests ==="
echo ""

# Create output directory
mkdir -p runs/demo

echo "1. Testing isolated audio loop (P2-01)..."
python -m drybox.core.runner \
    --scenario scenarios/audio_isolated_loop.yaml \
    --left adapters/audio_test.py:AudioTestAdapter \
    --right adapters/audio_test.py:AudioTestAdapter \
    --out runs/demo/isolated_loop \
    --tick-ms 20 --seed 42 --no-ui
echo "✓ Isolated loop test complete"
echo ""

echo "2. Testing AWGN channel (P2-02)..."
python -m drybox.core.runner \
    --scenario scenarios/audio_awgn_snr10.yaml \
    --left adapters/audio_test.py:AudioTestAdapter \
    --right adapters/audio_test.py:AudioTestAdapter \
    --out runs/demo/awgn \
    --tick-ms 20 --seed 42 --no-ui
echo "✓ AWGN channel test complete"
echo ""

echo "3. Testing Rayleigh fading (P2-03)..."
python -m drybox.core.runner \
    --scenario scenarios/audio_rayleigh_fading.yaml \
    --left adapters/audio_test.py:AudioTestAdapter \
    --right adapters/audio_test.py:AudioTestAdapter \
    --out runs/demo/fading \
    --tick-ms 20 --seed 42 --no-ui
echo "✓ Rayleigh fading test complete"
echo ""

echo "4. Testing AMR vocoder (P2-04)..."
python -m drybox.core.runner \
    --scenario scenarios/audio_amr_vocoder.yaml \
    --left adapters/audio_test.py:AudioTestAdapter \
    --right adapters/audio_test.py:AudioTestAdapter \
    --out runs/demo/vocoder \
    --tick-ms 20 --seed 42 --no-ui
echo "✓ AMR vocoder test complete"
echo ""

echo "5. Testing PLC with packet loss (P2-04)..."
python -m drybox.core.runner \
    --scenario scenarios/audio_plc_test.yaml \
    --left adapters/audio_test.py:AudioTestAdapter \
    --right adapters/audio_test.py:AudioTestAdapter \
    --out runs/demo/plc \
    --tick-ms 20 --seed 42 --no-ui
echo "✓ PLC test complete"
echo ""

echo "=== All tests completed successfully! ==="
echo ""
echo "Results available in:"
echo "  - runs/demo/isolated_loop/ - Basic audio loop"
echo "  - runs/demo/awgn/         - AWGN channel with SNR=10dB"
echo "  - runs/demo/fading/       - Rayleigh fading channel"
echo "  - runs/demo/vocoder/      - AMR vocoder with VAD/DTX"
echo "  - runs/demo/plc/          - Packet loss concealment"
echo ""
echo "To examine results:"
echo "  head runs/demo/*/metrics.csv"
echo "  jq '.type' runs/demo/*/events.jsonl | sort | uniq -c"