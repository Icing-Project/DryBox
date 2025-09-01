# DryBox × Nade — Architecture and Implementation Guide (DBX‑ABI v1)

> **Version**: 1.0 (beta)\
> **Audience**: Icing team (protocol, radio/DSP, networking, app), new contributors\
> **Goal**: provide a reproducible, minimal test bench for Nade — both **protocol logic** and **voice transport** — without over‑engineering.

---

## 0) TL;DR — What we’re building

- **DryBox** = headless simulator + client UI to “plug” **two virtual phones** (Nade endpoints) into a **simulated mobile network**.
- **Minimal, stable ABI** between DryBox and Nade: two complementary modes, **A: ByteLink** (opaque datagrams) and **B: AudioBlock** (fixed PCM blocks).
- DryBox **does not implement Nade**: it orchestrates, measures, perturbs the channel, and **does not depend** on Nade internals.

---

## 1) Objectives and non‑goals

### Objectives

1. **Validate Nade logic**: call FSM, Noise handshake (XK/XX), rekey, mux, TLV framing, adaptation.
2. **Assess “data‑over‑voice” feasibility**: modem (4FSK/…), FEC/interleaver, vocoder/RTCP impact, loss/jitter.
3. **Measure**: end‑to‑end latency, jitter, loss, BER/PER, goodput, handshake time, rekey, stability.
4. **Reproducible**: YAML scenarios, seeds, simulated clock.

### Non‑goals (v1)

- Model real IMS/SIP, SRVCC/CSFB, eNB/gNB QoS, HARQ/RLC/PDCP.
- Build a full phone (UI, real‑time audio I/O).
- Operational security/adversary side channels (temporal leakage) — out of initial scope.

---

## 2) Design principles

- **Strict separation**: DryBox (simulation/metrics) ≠ Nade (protocol).
- **Tiny, stable ABI**: 3 callbacks/mode + `nade_capabilities()`; backward compatible.
- **Headless first**: loop driven by a **simulated clock** (configurable Δt), UI subscribed via RPC.
- **Authoritative measurements**: timestamps at each layer boundary.
- **Declarative scenarios** (YAML) → no hard‑coded logic.
- **Plugin‑extensible**: new bearers, channels, vocoders without touching Nade or the modes.

---

## 3) Overview

```
           ┌──────────────┐           ┌──────────────┐
           │  Endpoint A  │           │  Endpoint B  │
           │    (Nade)    │           │    (Nade)    │
           └─────┬────────┘           └─────┬────────┘
                 │  DBX‑ABI v1 (Mode A: ByteLink  |  Mode B: AudioBlock)
        ┌────────▼─────────┐       ┌────────▼─────────┐
        │   Adapter A      │       │   Adapter B      │
        └───┬───────────┬──┘       └───┬───────────┬──┘
            │           │               │           │
      (opt) SAR‑lite    │         (B)  Channel/Vocoder/Modem
            │           │               │           │
        ┌───▼───┐   ┌───▼───┐       ┌───▼───┐   ┌───▼───┐
        │Bearer │ ← │Runner │  …    │Runner │ → │Bearer │
        └───────┘   └───────┘       └───────┘   └───────┘
```

---

## 4) The two modes (DBX‑ABI v1)

### 4.1. Mode A — **ByteLink** (protocol‑only)

**Purpose**: test **call FSM**, **Noise handshake**, **encrypted TLV framing**, **rekey**, **control/voice mux**, **adaptation** to network quality, **without** vocoder/audio effects.\
**What Nade sees**: an **opaque datagram link** (SDUs) subject to MTU/loss/jitter/reorder.\
**DryBox** may apply **SAR‑lite** (3‑byte fragmentation header) if `mtu_bytes` < SDU size.

**API**

```python
class NadeByteLink:
    def on_link_rx(self, sdu: bytes, t_ms: int) -> None: ...
    def poll_link_tx(self, budget: int) -> list[tuple[bytes, int]]: ...
    def on_timer(self, t_ms: int) -> None: ...
```

- `on_link_rx`: deliver a **complete** SDU to Nade.
- `poll_link_tx`: Nade exposes 0..N SDUs it wants to send with its logical `t_ms`.
- `on_timer`: periodic tick for Nade timers (retransmit, rekey, keepalive…).

**Use when**: developing logic, interop testing, framing fuzz, MTU variation, timeout studies.

---

### 4.2. Mode B — **AudioBlock** (voice chain)

**Purpose**: test **modems/FEC/interleaver**, robustness **through vocoders** (AMR/EVS/Opus mocks), jitter buffer, audio losses, CFO/clock.\
**What Nade sees**: **full‑duplex PCM blocks** (e.g., 8 kHz, 20 ms).\
**DryBox** applies channel/vocoder/jitter/PLC and measures BER/PER/lock.

**API**

```python
class NadeAudioPort:
    SAMPLE_RATE = 8000
    BLOCK_SAMPLES = 160  # 20 ms

    def pull_tx_block(self, t_ms: int) -> 'np.ndarray[int16]': ...
    def push_rx_block(self, pcm: 'np.ndarray[int16]', t_ms: int) -> None: ...
    def on_timer(self, t_ms: int) -> None: ...
```

- `pull_tx_block`: DryBox fetches the PCM block to transmit.
- `push_rx_block`: DryBox delivers the received block (post channel/vocoder).
- `on_timer`: internal cadence/coherence (AGC, modem reconfig…).

**Use when**: DSP work, data‑over‑voice validation, FEC/interleave tuning, BER‑SNR curves, codec compatibility.

---

### 4.3. Capability discovery (common)

```python
def nade_capabilities() -> dict:
    return {
      "bytelink": True,               # supports Mode A
      "audioblock": True,             # supports Mode B
      "audioparams": {"sr": 8000, "block": 160},
      "mtu": 256                      # preferred hint from Nade (Mode A)
    }
```

- Additional keys may be added in the future (backward compatible).

---

## 5) Runner & execution

- **Simulated clock** (`t_ms`): loop in steps (default 10 ms).
- **Two endpoints** loaded via adapters (Python module, sidecar binary, or FFI lib).
- **Bearers**: inject latency, jitter, loss, reorder, MTU; or audio+vocoder chain (Mode B).
- **SAR‑lite** (Mode A, optional): 3‑byte header `frag_id | idx | last`.
- **Metrics**: each layer boundary emits a timestamped event → CSV/JSON + visualization.

---

## 6) Scenarios (YAML)

**Generic schema**

```yaml
mode: byte | audio
name: "HS_rekey_lossy"
duration_ms: 60000
seed: 42
bearer:
  type: ott_udp | gsm_circuit | volte_evs
  latency_ms: 80
  jitter_ms: 20
  loss: 0.02
  reorder: 0.01
  mtu: 64                # Mode A
channel:                  # Mode B
  type: awgn | fading
  snr_db: 12
vocoder:                  # Mode B (mock)
  type: amr12k2_mock
  vad_dtx: true
```

**Example A — Handshake under loss (Mode A)**

```yaml
mode: byte
name: "xk_handshake_loss_10pct"
duration_ms: 15000
seed: 7
bearer: {type: ott_udp, latency_ms: 60, jitter_ms: 30, loss: 0.10, reorder: 0.01, mtu: 96}
```

**Example B — BER vs SNR (Mode B)**

```yaml
mode: audio
name: "4fsk_ber_snr_sweep"
duration_ms: 60000
seed: 11
bearer: {type: gsm_circuit, latency_ms: 120, jitter_ms: 25, loss: 0.01}
channel: {type: awgn, snr_db: [0, 5, 10, 15, 20]}
vocoder: {type: amr12k2_mock, vad_dtx: true}
```

---

## 7) Metrics & outputs

- **Transport (Mode A)**: estimated RTT, SDU end‑to‑end latency, jitter, loss, reorder, in‑order delivery, useful goodput.
- **Audio/Radio (Mode B)**: estimated SNR, CFO/clock jitter, modem lock ratio, **BER/PER**, resync rate, jitter‑buffer underruns.
- **Protocol**: handshake time, failure rate, rekey duration, post‑AEAD losses.
- **Exports**: `runs/<date>/<scenario>/metrics.csv`, `events.jsonl`, pcap‑like binaries (pre/post SAR, post bearer), plots (PNG).

---

## 8) Ready‑to‑code use cases

### Mode A

- **XK handshake with 10% loss + 1% reorder**: success < 1 s? zero deadlock.
- **Frames > MTU**: SDU 1 kB → MTU 64: correct reassembly; lost `idx=3` → clean abort/retry.
- **Rekey every 60 s**: no control/voice glitch (nonces/ssn OK).
- **Adaptation**: if PER>5% for 2 s → enable FEC / lower bitrate; revert when PER<1%.

### Mode B

- **BER‑SNR curve**: 4FSK 1200 baud, then add FEC r=1/2 + interleaver=5 frames.
- **VAD/DTX**: EVS/AMR mock, 400 ms silence → modem relock < 150 ms.
- **CFO 40 Hz & 50 ppm**: preamble false positives < 10⁻³.
- **100 ms burst drop**: audio loss → % of Nade frames passing AEAD.

---

## 9) Known limits & planned extensions

- **Mode A**: no vocoder/analog artifacts (use Mode B).
- **Mode B**: no “real” RTP/IMS; dynamic SR/block renegotiation not planned in v1.
- **Common**: no multi‑party/mixing (can be added in runner), no timing side‑channel security.\
  **Extensions**: more faithful RTP bearer, `capabilities_update` (audio renegotiation), A↔B bridge, multi‑endpoint, adversary model/temporal padding.

---

## 10) Repository layout (proposed)

```
 drybox/
   core/
     runner.py
     scenarios/             # YAML
     metrics.py
     logging.py
   net/
     bearers/
       ott_udp.py
       gsm_circuit.py
       volte_evs.py
     sar_lite.py            # 3B fragmentation (Mode A, optional)
   radio/
     channel_awgn.py
     channel_fading.py
     vocoder_models.py
   adapters/
     bytelink.py            # Mode A
     audioblock.py          # Mode B
     loader.py              # loads a Nade endpoint (module/lib/subprocess)
   ui/
     rpc_server.py
     client/                # Qt/Flutter → RPC
   tools/
     gen_scenario.py
     plot_timeline.py
```

---

## 11) API contracts (reference)

### 11.1. Common functions

```python
def nade_capabilities() -> dict: ...  # discovery
```

- Expected keys: `bytelink: bool`, `audioblock: bool`, `audioparams: {sr:int, block:int}`, `mtu: int`.
- Free to add extensions.

### 11.2. Mode A — ByteLink

```python
class NadeByteLink:
    def on_link_rx(self, sdu: bytes, t_ms: int) -> None: ...
    def poll_link_tx(self, budget: int) -> list[tuple[bytes, int]]: ...
    def on_timer(self, t_ms: int) -> None: ...
```

**DryBox guarantees**: `on_link_rx` delivers a **complete** SDU (defragmented if SAR‑lite active).\
**DryBox expects**: `poll_link_tx(budget)` returns ≤ `budget` SDUs.

### 11.3. Mode B — AudioBlock

```python
class NadeAudioPort:
    SAMPLE_RATE: int
    BLOCK_SAMPLES: int
    def pull_tx_block(self, t_ms: int) -> 'np.ndarray[int16]': ...
    def push_rx_block(self, pcm: 'np.ndarray[int16]', t_ms: int) -> None: ...
    def on_timer(self, t_ms: int) -> None: ...
```

**DryBox guarantees**: regular cadence of `BLOCK_SAMPLES` per `t_ms` (e.g., 20 ms).\
**DryBox expects**: `pull_tx_block` always returns a full buffer (zero‑pad for silence if needed).

### 11.4. Threading & timing

- DryBox calls callbacks **on the runner thread** (no concurrent re‑entry).
- `t_ms` is **logical** and monotonic (simulated clock).
- Endpoints **must not block** (bounded budget, bounded buffers).

---

## 12) Developer quick‑start

1. **Clone** DryBox and Nade.
2. On the Nade side, provide a `nade_adapter.py` exposing `nade_capabilities()` and a class for the chosen mode.
3. In `scenarios/`, create a YAML (e.g., `xk_handshake_loss_10pct.yaml`).
4. Run: `python -m drybox.core.runner --scenario scenarios/xk_handshake_loss_10pct.yaml --left nade_adapter.py --right nade_adapter.py`
5. Inspect `runs/<date>/<scenario>/metrics.csv` and the UI (if launched) for visualization.

---

## 13) Testing & quality

- **Unit**: SAR‑lite (fragment/reasm), bearers (latency/jitter/loss), scheduler, scenario parsers.
- **Property‑based**: fuzz MTU/lengths/fragment order, burst losses.
- **Integration**: “gold” scenarios (see §8) with target thresholds (e.g., handshake success < 1 s @ 10% loss).
- **CI**: `pytest -q`, `ruff`, `mypy` (if typed Py), metrics artifacts as job outputs.

---

## 14) Governance & contributions

- **Issue labels**: `mode-a`, `mode-b`, `bearer`, `metrics`, `runner`, `ui`.
- **PRs**: tests required; no dependency from DryBox to Nade (only via `adapters/loader.py`).
- **Style**: PEP 8/pyproject, docstrings, structured logs (JSON) at `INFO` for metrics.

---

## 15) Suggested roadmap (2 sprints)

**Sprint 1 (core v1)**: runner, full Mode A (ott\_udp + SAR‑lite), 3 scenarios, metrics export, CLI.\
**Sprint 2 (audio v1)**: Mode B (gsm\_circuit + AWGN + vocoder mock), BER‑SNR sweep, minimal UI (timeline + scopes).\
**+**: add `volte_evs` mock, CFO/clock jitter, basic interleaver+FEC.

---

## 16) Glossary

- **SDU**: Service Data Unit (logical unit seen by Nade).
- **PDU**: Protocol Data Unit (unit carried by the bearer).
- **SAR**: Segmentation And Reassembly.
- **PLC**: Packet Loss Concealment.
- **CFO**: Carrier Frequency Offset.
- **VAD/DTX**: Voice Activity Detection / Discontinuous Transmission.

---

### Appendix A — SAR‑lite header (Mode A, optional)

- 3 bytes: `frag_id (8b)` | `idx (8b)` | `last (8b)`
- Group by `(frag_id)`; `last=1` on the final fragment.
- No ARQ/FEC in v1 (robustness evaluated via `loss/reorder` scenarios).

### Appendix B — Acceptance set (extracts)

- **XK HS @ 10% loss**: T\_HS ≤ 1 s; 0 deadlocks; 0 invalid AEAD frames.
- **4FSK @ SNR = 10 dB**: BER ≤ 10⁻³ without FEC; BER ≤ 10⁻⁴ with FEC r=1/2 + interleave 5.
- **100 ms burst** (Mode B): modem relock ≤ 150 ms; Nade PDU loss ≤ 5% over 2 s window.

---

> **Contact**: open an issue with the `proposal:` prefix for any ABI extension or new bearer.

