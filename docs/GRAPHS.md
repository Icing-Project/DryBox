# DryBox Metrics Graphs Documentation

This document explains the real-time visualization graphs available in the DryBox GUI simulator. These graphs help monitor the quality and performance of encrypted voice communication simulations.

## Overview

DryBox provides two simulation modes:
- **Byte Mode (ByteLink)**: Tests protocol logic, Noise handshake, encrypted TLV framing
- **Audio Mode (AudioBlock)**: Tests voice transport, FSK modems, vocoders, channel effects

Each mode displays different graphs relevant to its metrics.

---

## Byte Mode Graphs

### 1. Network Metrics Graph (Loss Rate & Reorder Rate)

**Purpose**: Monitor packet delivery reliability in the simulated network.

| Metric | Description | Color |
|--------|-------------|-------|
| Loss Rate | Fraction of packets dropped (0-1 scale) | Red |
| Reorder Rate | Fraction of packets arriving out of order (0-1 scale) | Orange |

**Why it's useful**:
- **Loss Rate** directly impacts call quality. High loss (>5%) causes audible gaps and codec artifacts
- **Reorder Rate** indicates network instability. High reordering can cause buffer underruns and increased latency
- Comparing L→R vs R→L reveals asymmetric network conditions

**Typical Values**:
- Excellent: Loss <1%, Reorder <1%
- Acceptable: Loss <5%, Reorder <3%
- Poor: Loss >10% (noticeable degradation)


### 2. Jitter Graph

**Purpose**: Monitor variation in packet arrival times.

| Metric | Description | Color |
|--------|-------------|-------|
| L→R Jitter | Arrival time variance for Left→Right direction | Blue |
| R→L Jitter | Arrival time variance for Right→Left direction | Purple |

**Why it's useful**:
- High jitter requires larger jitter buffers, increasing end-to-end latency
- Consistent jitter is easier to compensate than bursty jitter
- Voice codecs (especially low-bitrate) are sensitive to jitter

**Typical Values**:
- Excellent: <10ms
- Acceptable: 10-30ms
- Poor: >50ms (requires large buffers, noticeable delay)


### 3. Goodput Graph

**Purpose**: Monitor actual useful data throughput (excluding overhead).

| Metric | Description | Color |
|--------|-------------|-------|
| L→R Goodput | Effective throughput Left→Right | Green |
| R→L Goodput | Effective throughput Right→Left | Teal |

**Why it's useful**:
- **Goodput ≠ Bandwidth**: Goodput excludes retransmissions, headers, and encryption overhead
- Reveals actual encrypted payload capacity
- Dropping goodput may indicate congestion or increasing loss
- Essential for validating that the Nade protocol achieves expected throughput

**Typical Values**:
- Voice-only: 10-20 kbps (codec-dependent)
- With overhead: 15-30 kbps
- Maximum (saturated link): depends on bearer configuration


### 4. RTT Graph (Round-Trip Time)

**Purpose**: Monitor end-to-end latency estimation.

| Metric | Description | Color |
|--------|-------------|-------|
| RTT | Estimated round-trip time | Orange |

**Why it's useful**:
- RTT directly affects conversational quality (>300ms feels unnatural)
- High RTT impacts Noise handshake completion time
- RTT spikes may indicate network congestion
- Used by SAR reassembly timeout calculations

**Typical Values**:
- VoLTE (same region): 50-100ms
- GSM circuit-switched: 100-200ms
- International/satellite: 300-600ms

---

## Audio Mode Graphs

### 5. SNR Graph (Signal-to-Noise Ratio)

**Purpose**: Monitor signal quality through the simulated radio channel.

| Metric | Description | Color |
|--------|-------------|-------|
| SNR | Signal-to-Noise Ratio in decibels | Blue |

**Why it's useful**:
- SNR determines modem demodulation reliability
- Low SNR (<10dB) causes bit errors and frame loss
- Tracks channel conditions over time (fading, interference)
- Essential for validating FSK modem performance

**Typical Values**:
- Excellent: >25dB (error-free)
- Good: 15-25dB (occasional errors)
- Marginal: 10-15dB (increased BER)
- Poor: <10dB (high error rate, possible sync loss)


### 6. BER/PER Graph (Error Rates)

**Purpose**: Monitor transmission error rates.

| Metric | Description | Color |
|--------|-------------|-------|
| BER | Bit Error Rate (errors per bit transmitted) | Red |
| PER | Packet Error Rate (lost frames per total frames) | Purple |

**Why it's useful**:
- **BER** measures raw channel quality before error correction
- **PER** measures post-FEC frame loss (what the decoder sees)
- High BER with low PER = FEC working effectively
- Both high = channel conditions too poor for reliable communication

**Typical Values**:
- BER Excellent: <10^-4 (0.0001)
- BER Acceptable: <10^-3 (0.001)
- PER Excellent: <1% (0.01)
- PER Acceptable: <5%
- PER Poor: >10% (audible degradation)

---

## Summary Statistics Panel

After each simulation run, a summary panel displays aggregated statistics:

| Statistic | Description |
|-----------|-------------|
| Duration | Total simulation time in milliseconds |
| Mode | BYTE or AUDIO |
| Avg Loss L→R/R→L | Mean packet loss rate per direction |
| Avg Jitter L→R/R→L | Mean jitter per direction |
| Avg RTT | Mean round-trip time estimation |
| Avg Goodput L→R/R→L | Mean throughput per direction |
| Avg SNR | Mean signal-to-noise ratio (audio mode) |
| Avg BER | Mean bit error rate (audio mode) |
| Frame Loss Rate | Total frames lost / total frames (audio mode) |

**Why it's useful**:
- Quick pass/fail assessment of simulation quality
- Compare runs with different configurations
- Identify which metrics degraded most
- Generate reports for validation

---

## Graph Architecture

### Data Flow
```
Runner (CLI) → stderr output → RunnerThread → metrics parsing → Signal → Graph widgets
```

### Update Frequency
- Graphs update every 1 second (matching runner UI output interval)
- Rolling window of last 100 data points
- Summary statistics accumulate across entire run

### Mode Switching
- Graphs automatically show/hide based on current simulation mode
- Byte mode: Network, Jitter, Goodput, RTT graphs
- Audio mode: SNR, BER/PER graphs
- Summary panel visible in both modes

---

## Interpreting Results

### Healthy Byte Mode Run
- Loss rate stays <5%
- Jitter relatively constant <30ms
- Goodput matches expected throughput
- RTT stable around configured latency

### Healthy Audio Mode Run
- SNR stays >15dB
- BER <0.001
- PER <5%
- Consistent SNR without deep fades

### Warning Signs
- Sudden loss spikes: network congestion or bearer failure
- RTT climbing: buffer bloat or routing changes
- SNR oscillating: Rayleigh fading effects
- BER high but PER low: FEC working hard (marginal conditions)
- Both BER and PER high: channel too degraded

---

## Configuration Tips

### To see more network impairments (Byte Mode):
```yaml
network:
  bearer: volte_evs
  loss_rate: 0.05      # 5% loss
  reorder_rate: 0.02   # 2% reordering
  jitter_ms: 20        # 20ms jitter
  latency_ms: 50       # 50ms one-way latency
```

### To see radio channel effects (Audio Mode):
```yaml
left:
  modem:
    channel_type: rayleigh  # Fading channel
    snr_db: 15              # Moderate SNR
    doppler_hz: 50          # Vehicle speed Doppler
    vocoder: amr12k2        # AMR codec simulation
```

---

## Technical Notes

- Graphs use PyQtGraph for efficient real-time rendering
- Metrics parsed via regex from runner stderr output
- Summary stats calculated using online averaging (no memory explosion)
- All graphs auto-scale Y-axis for better visibility
