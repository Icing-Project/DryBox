# DryBox - Encrypted Voice Communication Simulator

DryBox is a test bench for validating the **Nade protocol** (Noise-Authenticated Duplex Encryption) in voice transport scenarios. It simulates two virtual phones connecting through a network with controllable impairments.

## Features

- **Two simulation modes**: ByteLink (protocol testing) and AudioBlock (voice transport)
- **Real-time visualization**: Network metrics, SNR, error rates, throughput graphs
- **Network impairment simulation**: Packet loss, jitter, reordering, latency
- **Radio channel models**: AWGN noise, Rayleigh fading with Doppler
- **Vocoder simulation**: AMR, EVS, Opus codec mocks with packet loss concealment
- **Audio file testing**: Load WAV files for realistic voice testing
- **Deterministic simulation**: Seeded RNG for reproducible results

## Quick Start

### Installation

```bash
cd /home/bartosz/delivery/EIP/DryBox
uv sync  # Install dependencies
```

### Run the GUI

```bash
uv run -m drybox.gui.app
```

### Run from Command Line

```bash
uv run -m drybox.core.runner \
  --scenario scenarios/audio_file_test.yaml \
  --left adapters/audio_file_adapter.py:AudioFileAdapter \
  --right adapters/audio_file_adapter.py:AudioFileAdapter \
  --out runs/my_test
```

## Project Structure

```
DryBox/
├── drybox/
│   ├── core/           # Simulation engine
│   │   ├── runner.py   # Main simulation loop
│   │   ├── scenario.py # Scenario loading/validation
│   │   └── metrics.py  # Metrics output (CSV, JSON)
│   ├── gui/            # Qt GUI application
│   │   ├── app.py      # Main window
│   │   ├── pages/      # Tab pages (General, Adapters, Runner)
│   │   └── widgets/    # Graph widgets
│   ├── net/            # Network simulation
│   │   ├── bearers.py  # Bearer models (VoLTE, GSM, etc.)
│   │   └── sar_lite.py # Segmentation & reassembly
│   ├── radio/          # Radio channel simulation
│   │   ├── channel_awgn.py    # AWGN channel
│   │   ├── channel_fading.py  # Rayleigh fading
│   │   └── vocoder_models.py  # Codec mocks
│   └── schema/         # JSON schemas for validation
├── adapters/           # Adapter implementations
├── scenarios/          # Example scenario files
├── runs/               # Simulation output directory
└── docs/               # Additional documentation
```

## Simulation Modes

### Mode A: ByteLink (Protocol Testing)

Tests the Nade protocol at the byte level:
- Noise XK handshake
- Encrypted TLV framing
- Rekey operations
- Control/voice multiplexing

**Metrics tracked**: Loss rate, reorder rate, jitter, latency, RTT, goodput

### Mode B: AudioBlock (Voice Transport)

Tests voice transmission through simulated radio channels:
- FSK modem simulation
- Vocoder encode/decode
- Channel impairments (noise, fading)
- Packet loss concealment

**Metrics tracked**: SNR, BER, PER, frame loss

## Configuration

### Scenario File (YAML)

```yaml
mode: audio              # 'audio' or 'byte'
duration_ms: 10000       # Simulation duration
seed: 42                 # Random seed for reproducibility

network:
  bearer: volte_evs      # volte_evs, cs_gsm, pstn_g711, ott_udp
  latency_ms: 50         # One-way latency
  jitter_ms: 10          # Jitter variation
  loss_rate: 0.05        # Packet loss (0-1)
  reorder_rate: 0.02     # Reordering rate (0-1)

left:
  adapter: audio_file_adapter.py
  gain: 1.0
  modem:
    audio_file: /path/to/audio.wav
    loop: true
    channel_type: awgn   # none, awgn, fading
    snr_db: 15           # Signal-to-noise ratio
    vocoder: amr12k2_mock

right:
  adapter: audio_file_adapter.py
  gain: 1.0
  modem:
    channel_type: none
    vocoder: none
```

### Bearer Types

| Bearer | Description | Typical Use |
|--------|-------------|-------------|
| `volte_evs` | VoLTE with EVS codec | Modern 4G/5G voice |
| `cs_gsm` | Circuit-switched GSM | Legacy 2G/3G |
| `pstn_g711` | PSTN with G.711 | Landline simulation |
| `ott_udp` | Over-the-top UDP | VoIP apps |

### Channel Types

| Channel | Description | Parameters |
|---------|-------------|------------|
| `none` | No impairment | - |
| `awgn` | Additive White Gaussian Noise | `snr_db` |
| `fading` | Rayleigh fading | `snr_db`, `doppler_hz`, `num_paths` |

### Vocoders

| Vocoder | Description |
|---------|-------------|
| `none` | Pass-through (no codec) |
| `amr12k2_mock` | AMR 12.2 kbps simulation |
| `evs13k2_mock` | EVS 13.2 kbps simulation |
| `opus_nb_mock` | Opus narrowband simulation |

## GUI Usage

### General Tab
- Set simulation mode (audio/byte)
- Configure duration and random seed
- Set network parameters (bearer, loss, jitter, latency)

### Adapters Tab
- Select left and right adapters
- Configure adapter-specific settings

### Runner Tab
- Click **Run** to start simulation
- View real-time graphs and metrics
- Resize panels by dragging borders
- View log output and summary statistics

### Graph Panels

**Byte Mode:**
- Network Metrics (loss rate, reorder rate)
- Jitter (L→R, R→L)
- Goodput (throughput)
- RTT (round-trip time)

**Audio Mode:**
- SNR (signal-to-noise ratio)
- BER/PER (bit/packet error rates)
- Frame Statistics (total vs lost)

## Audio File Testing

### Requirements
- Format: WAV (16-bit PCM)
- Sample rate: 8000 Hz
- Channels: Mono

### Convert Audio Files

```bash
# Convert any audio to compatible format
ffmpeg -i input.mp3 -ar 8000 -ac 1 -sample_fmt s16 output.wav
```

### Using Audio Files

1. Place WAV file in `drybox/WAV/` directory
2. Create scenario with `audio_file` parameter:
   ```yaml
   left:
     modem:
       audio_file: /path/to/audio.wav
       loop: true
   ```
3. Run with `audio_file_adapter.py`

## Output Files

Each simulation run creates:

| File | Description |
|------|-------------|
| `metrics.csv` | Timestamped metrics data |
| `events.jsonl` | Custom adapter events |
| `capture.dbxcap` | Binary packet capture |
| `scenario.resolved.yaml` | Final resolved configuration |
| `pubkeys.txt` | Cryptographic key info |

## Writing Custom Adapters

Adapters must implement the following interface:

```python
class MyAdapter:
    def nade_capabilities(self) -> dict:
        """Declare supported modes"""
        return {"bytelink": True, "audioblock": True}

    def init(self, cfg: dict) -> None:
        """Initialize with configuration"""
        pass

    def start(self, ctx) -> None:
        """Start adapter with context"""
        pass

    def on_timer(self, t_ms: int) -> None:
        """Called every tick"""
        pass

    # ByteLink mode
    def on_link_rx(self, sdu: bytes) -> None:
        """Receive data"""
        pass

    def poll_link_tx(self, budget: int) -> list:
        """Send data"""
        return []

    # AudioBlock mode
    def push_tx_block(self, t_ms: int) -> np.ndarray:
        """Return 160 samples of int16 PCM"""
        return np.zeros(160, dtype=np.int16)

    def pull_rx_block(self, pcm: np.ndarray, t_ms: int) -> None:
        """Receive processed audio"""
        pass
```

## Troubleshooting

### No graphs showing
- Ensure simulation is running (check progress bar)
- Check log for errors
- Verify scenario file is valid YAML

### SNR shows 'inf'
- Normal for silent audio (no signal = infinite SNR)
- Use audio files with continuous speech
- Set `loop: true` to avoid silence at end

### Audio file not loading
- Check file is 8kHz mono WAV
- Verify path in scenario is correct
- Check log for "audio_file_loaded" event

### Simulation fails immediately
- Check scenario YAML syntax
- Verify adapter paths are correct
- Look for schema validation errors in log

## Dependencies

- Python 3.11+
- PySide6 (Qt GUI)
- PyQtGraph (real-time graphs)
- NumPy (numerical processing)
- PyYAML (configuration)
- cryptography (Noise protocol)

## License

MIT License
