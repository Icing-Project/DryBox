# DryBox Quick Start Guide

## 1. Run the GUI (Easiest)

```bash
cd /home/bartosz/delivery/EIP/DryBox
uv run -m drybox.gui.app
```

Then:
1. **General tab**: Set mode to `audio`, duration to `10000`
2. **Adapters tab**: Select adapters for both sides
3. **Runner tab**: Click Run, watch the graphs

## 2. Run from Command Line

### Basic Audio Test
```bash
uv run -m drybox.core.runner \
  --scenario scenarios/audio_file_test.yaml \
  --left adapters/audio_file_adapter.py:AudioFileAdapter \
  --right adapters/audio_file_adapter.py:AudioFileAdapter \
  --out runs/test1
```

### With Custom Scenario
```bash
# Create your scenario
cat > my_scenario.yaml << 'EOF'
mode: audio
duration_ms: 5000
seed: 42
network:
  bearer: volte_evs
  loss_rate: 0.1
left:
  adapter: test_traffic_adapter.py
  gain: 1.0
  modem:
    channel_type: awgn
    snr_db: 20
right:
  adapter: test_traffic_adapter.py
  gain: 1.0
  modem: {}
EOF

# Run it
uv run -m drybox.core.runner \
  --scenario my_scenario.yaml \
  --left adapters/test_traffic_adapter.py:Adapter \
  --right adapters/test_traffic_adapter.py:Adapter \
  --out runs/custom
```

## 3. Test with Your Own Audio

### Step 1: Convert your audio
```bash
ffmpeg -i your_audio.mp3 -ar 8000 -ac 1 -sample_fmt s16 drybox/WAV/my_audio.wav
```

### Step 2: Update scenario
Edit `scenarios/audio_file_test.yaml`:
```yaml
left:
  modem:
    audio_file: /full/path/to/drybox/WAV/my_audio.wav
    loop: true
```

### Step 3: Run
```bash
uv run -m drybox.core.runner \
  --scenario scenarios/audio_file_test.yaml \
  --left adapters/audio_file_adapter.py:AudioFileAdapter \
  --right adapters/audio_file_adapter.py:AudioFileAdapter \
  --out runs/my_audio_test
```

## 4. View Results

After a run, check the output directory:
```bash
ls runs/test1/
# metrics.csv      - All metrics data
# events.jsonl     - Event log
# capture.dbxcap   - Packet capture
```

View metrics:
```bash
head runs/test1/metrics.csv
```

## 5. Common Configurations

### High Loss Network
```yaml
network:
  bearer: volte_evs
  loss_rate: 0.15      # 15% loss
  jitter_ms: 30
```

### Noisy Channel
```yaml
left:
  modem:
    channel_type: awgn
    snr_db: 10         # Low SNR = more noise
```

### Fading Channel (Mobile)
```yaml
left:
  modem:
    channel_type: fading
    snr_db: 15
    doppler_hz: 100    # High speed vehicle
```

### With Vocoder
```yaml
left:
  modem:
    vocoder: amr12k2_mock
    channel_type: awgn
    snr_db: 20
```

## 6. GUI Tips

- **Resize panels**: Drag the borders between graphs and console
- **Clear graphs**: They auto-clear when you start a new run
- **Summary stats**: Appear at bottom after run completes
- **Mode switching**: Graphs auto-switch between byte/audio mode

## 7. Available Adapters

| Adapter | Description |
|---------|-------------|
| `audio_file_adapter.py:AudioFileAdapter` | Play WAV files |
| `test_traffic_adapter.py:Adapter` | Generate test tones |
| `nade_adapter.py:Adapter` | Full Nade protocol |

## 8. Troubleshooting

**"No such file" error**
→ Use absolute paths in scenario YAML

**Graphs empty**
→ Check console log for errors

**SNR shows 99dB**
→ Audio is silent; use `loop: true` or different file

**Schema validation error**
→ Check YAML syntax; use provided examples as template
