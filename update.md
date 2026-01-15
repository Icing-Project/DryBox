# DryBox Updates - January 6, 2026

## Session Summary

### 1. Fixed DryBox Entry Point
- Updated `pyproject.toml` to fix the GUI entry point from `drybox.ui.__main__:main` to `drybox.gui.app:main`

### 2. Added Real-Time Metrics Graphs
Replaced placeholder graphs with functional real-time visualization:

**New files created:**
- `drybox/gui/widgets/__init__.py`
- `drybox/gui/widgets/metrics_graphs.py` - Contains graph widgets using pyqtgraph

**Modified files:**
- `drybox/gui/runner/runner_thread.py` - Added metrics signal and parsing for real-time metrics data
- `drybox/gui/pages/runner_page.py` - Integrated graph widgets and connected to metrics signal
- `pyproject.toml` - Added `pyqtgraph>=0.13.0` dependency

**Graph Features:**
- **Left Panel (Network Quality):**
  - Loss Rate over time (red line)
  - Reorder Rate over time (orange line)
  - Jitter graph (L→R blue, R→L purple)

- **Right Panel (Direction Comparison):**
  - L→R network metrics
  - R→L network metrics

- Graphs automatically switch between byte mode and audio mode visualizations
- Real-time updates during simulation runs
- Progress bar now accurately tracks simulation progress based on duration_ms

### How to Run DryBox
From the nade-python directory:
```bash
cd /home/bartosz/delivery/Nade-Python
uv run -m drybox.gui.app
```

Select `/home/bartosz/delivery/Nade-Python/adapter/drybox_adapter.py` as both left and right adapters.

---

# DryBox Updates - January 15, 2026

## Session Summary: Enhanced Metrics Visualization

### 1. Extended Runner Output Format
Updated `drybox/core/runner.py` to output additional metrics to stderr:

**Byte Mode** now includes:
- RTT estimation (ms)
- Goodput L→R and R→L (bps)

**Audio Mode** now includes:
- SNR (Signal-to-Noise Ratio in dB)
- BER (Bit Error Rate)
- PER (Packet Error Rate)
- Total frames and lost frames count

### 2. Enhanced Metrics Parsing
Updated `drybox/gui/runner/runner_thread.py`:
- Extended regex patterns to parse new metrics
- Handles both legacy and enhanced output formats
- Parses optional extended metrics when present

### 3. New Graph Widgets
Added new visualizations in `drybox/gui/widgets/metrics_graphs.py`:

**Byte Mode Graphs:**
| Graph | Description |
|-------|-------------|
| GoodputGraph | Shows L→R and R→L throughput in bps |
| RTTGraph | Shows Round-Trip Time estimation |

**Audio Mode Graphs:**
| Graph | Description |
|-------|-------------|
| SNRGraph | Shows Signal-to-Noise Ratio (dB) |
| BERPERGraph | Shows Bit Error Rate and Packet Error Rate |

**Summary Statistics Widget:**
- Displays aggregated stats after simulation completes
- Shows averages for all metrics
- Includes duration, mode, loss rates, jitter, RTT, goodput, SNR, BER, frame loss

**EnhancedCombinedMetricsGraph:**
- New container widget that combines all graphs
- Auto-switches visibility based on byte/audio mode
- Includes summary stats panel

### 4. Updated Runner Page
Modified `drybox/gui/pages/runner_page.py`:
- Replaced `CombinedMetricsGraph` with `EnhancedCombinedMetricsGraph`
- Added finalize() call on run completion to display summary stats

### 5. Documentation
Created `GRAPHS.md` with comprehensive documentation:
- Explanation of each graph and its metrics
- Why each metric matters for voice communication quality
- Typical values and thresholds
- Configuration tips
- Technical architecture notes

### Files Modified
- `drybox/core/runner.py` - Extended stderr output format
- `drybox/gui/runner/runner_thread.py` - Enhanced metrics parsing
- `drybox/gui/widgets/metrics_graphs.py` - Added 6 new widget classes
- `drybox/gui/pages/runner_page.py` - Integrated enhanced graphs

### Files Created
- `GRAPHS.md` - Documentation for all metrics graphs

---

# DryBox Updates - January 15, 2026 (Session 2)

## Session Summary: UI Improvements & Audio File Testing

### 1. Fixed Duplicate Audio Mode Graphs
**Problem**: Both left and right panels showed "Audio Mode Progress" graphs in audio mode.

**Solution**:
- Replaced redundant `AudioModeGraph` in `DualDirectionMetricsGraph` with new `FrameStatsGraph`
- `FrameStatsGraph` shows Total Frames vs Lost Frames over time
- Left panel shows SNR + BER/PER graphs, right panel shows frame statistics

### 2. Added Resizable Splitters
**Problem**: Could not resize graph panels or console area.

**Solution**: Updated `runner_page.py` with `QSplitter` widgets:
- Horizontal splitter between left and right graph panels
- Vertical splitter between graphs and console
- Default ratio: 70% graphs, 30% console
- Users can drag borders to resize

### 3. Summary Statistics Panel
The summary stats panel is part of `EnhancedCombinedMetricsGraph` and displays:
- Duration, Mode
- Average loss rates (L→R, R→L)
- Average jitter (L→R, R→L)
- Average RTT, Goodput
- Audio mode: Average SNR, BER, Frame Loss Rate

Stats are calculated during simulation and finalized when run completes.

### 4. Audio File Testing Support
**New Feature**: Created `adapters/audio_file_adapter.py` for testing with real audio files.

**Usage**:
```yaml
mode: audio
duration_ms: 10000
left:
  modem:
    audio_file: /path/to/speech.wav
    loop: true
```

**Requirements for audio files**:
- Format: WAV (16-bit PCM)
- Sample rate: 8000 Hz (narrowband)
- Channels: Mono

**Convert existing files with ffmpeg**:
```bash
ffmpeg -i input.mp3 -ar 8000 -ac 1 -sample_fmt s16 output.wav
```

**To run with audio file**:
```bash
cd /home/bartosz/delivery/EIP/DryBox
uv run -m drybox.core.runner \
  --scenario scenarios/your_scenario.yaml \
  --left adapters/audio_file_adapter.py:AudioFileAdapter \
  --right adapters/audio_file_adapter.py:AudioFileAdapter \
  --out runs/audio_test
```

### Files Modified
- `drybox/gui/pages/runner_page.py` - Added QSplitter for resizable panels
- `drybox/gui/widgets/metrics_graphs.py` - Added FrameStatsGraph, fixed audio mode display

### Files Created
- `adapters/audio_file_adapter.py` - Audio file playback adapter

### Additional Fixes (Session 2 continued)
- Fixed runner to pass modem config to adapters (`runner.py` line 174)
- Fixed audio metrics regex to handle 'inf' SNR values (`runner_thread.py`)
- Updated scenario schema to allow `audio_file` and `loop` properties
- Created `scenarios/audio_file_test.yaml` example scenario

### Documentation Added
- `README.md` - Comprehensive project documentation
- `docs/QUICKSTART.md` - Quick start guide with examples
- `GRAPHS.md` - Detailed graph/metrics documentation
