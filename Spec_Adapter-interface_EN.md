# DryBox v1 — Comprehensive specification for communicating with adapters (left & right)

> Goal: write/validate **adapter interfaces** (Nade or others) that plug into DryBox, in **Mode A: ByteLink** (opaque datagrams) and **Mode B: AudioBlock** (PCM blocks). This doc formalizes the **lifecycle**, **timing semantics**, **signatures**, **memory** (PCM), **SAR-lite fragmentation**, **capability discovery**, **error handling**, **thread safety**, **events/metrics**, and provides **examples** and **conformance tests**. Architecture reference: DBX-ABI v1.

---

## 1) Execution model (runner ↔ adapters)

### 1.1 Time loop (simulated clock)

* Logical **tick**: `t_ms` (default **10 ms**). **At each tick**:

  1. `on_timer(t_ms)` is called **first** on `left`, then on `right`.
  2. **I/O by mode**:

     * **Mode A** (ByteLink): `poll_link_tx(budget)` (left → enqueue to bearer) then (right → enqueue); the bearer delivers the PDUs **that arrive** at this tick, DryBox calls `on_link_rx(...)` on the destination peer **in arrival order** (reordering may occur depending on the bearer).
     * **Mode B** (AudioBlock): `pull_tx_block()` (left & right), pass through **channel/vocoder/PLC**, then deliver via `push_rx_block()` to the peer.
  3. Emit per-tick **metrics**.
* `t_ms` is **monotonic**, decoupled from the system clock; **no sleep** is expected on the adapter side (**deterministic**).

### 1.2 Loading & lifecycle (Python module v1)

* Load adapters by path `path/to/adapter.py:ClassName`.
* **Lifecycle**: `__init__()` → `init(cfg)` (optional) → `start(ctx)` → (per‑tick callbacks) → `stop()` (optional).
* `cfg` is an opaque dict. In v1 DryBox includes at least:
  - `side`: `"L"` or `"R"`
  - `tick_ms`, `seed`, `mode`, `sdu_max_bytes`, `out_dir`
  - `crypto`: see §2.3 (if available; contains `{priv, pub, peer_pub, key_id, peer_key_id}`)

* `ctx` is a stable execution context with:
  - `now_ms()` → current **logical** time
  - `emit_event(type: str, payload: dict)` → writes to `events.jsonl`
  - `rng` (deterministic, seeded by DryBox)
  - `config` (the same `cfg` dict passed to `init()`)

Adapters must be **non‑blocking**. All callbacks are invoked on the runner thread (no concurrent re‑entry).


### 1.3 Threading

* All callbacks of an adapter are invoked **on the runner’s thread**, with **no concurrent re-entry**. Adapters **must not block** (design bounded buffers and O(1)/bounded O(n) processing per tick).

---

## 2) Capability discovery (negotiation-lite)

### 2.1 Input

```python
def nade_capabilities() -> dict:
    return {
        "abi_version": "1.0",
        "bytelink": true | false,
        "audioblock": true | false,
        "sdu_max_bytes": 1024,             # max SDU before SAR (Mode A)
        "audioparams": { "sr": 8000, "block": 160 }  # optional (Mode B)
    }
```

* **Required**: `abi_version="1.0"`.
* **Mode A**: `sdu_max_bytes` (default **1024**).
* **Mode B**: in v1 DryBox **defaults** to NB 8 kHz, **20 ms** block (160 samples), but the adapter may **announce** `audioparams` (the v1 implementation is fixed at 8 kHz/20 ms).

### 2.2 Implicit agreement

* In v1, DryBox **negotiates minimally**: if a mode isn’t supported, it **fails the run** (exit 3). If `audioparams` diverge, DryBox v1 prefers its scenario/default parameters (renegotiation extension to come).

### 2.3 Cryptographic provisioning (Ed25519, v1)

DryBox can provide per‑side Ed25519 key material to adapters via `cfg["crypto"]`. For each side (L/R):

- `priv`: 32‑byte private seed (Ed25519)
- `pub`: 32‑byte public key
- `peer_pub`: 32‑byte peer public key
- `key_id`: hex short ID for `pub` (first 8 hex chars of SHA‑256(pub))
- `peer_key_id`: short ID for `peer_pub`

**Where keys come from**

1. **Scenario‑provided** (optional): under `crypto.left_priv` and/or `crypto.right_priv`, accepted forms:
   - `{hex: "<64 hex chars>"}` or `{b64: "<base64>"}` or `{path: "file"}`.
   - 32‑byte seeds preferred; 64‑byte extended keys are accepted and truncated to 32.
   - Invalid inputs cause **exit 4** (invalid scenario).

2. **Otherwise derived** deterministically via HKDF‑SHA256 from `(seed, left_adapter_spec, right_adapter_spec, side)` so sweeps (e.g., `snr_db=[...]`) **do not change keys**.

DryBox **never** writes private keys to disk. It emits `runs/.../pubkeys.txt` with public keys and IDs only, for interop debugging.

> This provisioning is **ABI‑agnostic**: adapters may ignore `cfg["crypto"]` if they don’t need authentication. (Reference mock: the PingPong adapter uses domain‑separated Ed25519 signatures in its handshake.)

---

## 3) Mode A — ByteLink (opaque datagrams)

### 3.1 API contract (Mode A — ByteLink)

```python
class NadeByteLink:
    def on_link_rx(self, sdu: bytes) -> None: ...
    def poll_link_tx(self, budget: int) -> list[bytes]: ...
    def on_timer(self, t_ms: int) -> None: ...
```

* `on_link_rx(sdu)`: DryBox delivers a **complete SDU** (defragmented if SAR-lite is active). **Arrival order** may be **reordered** (network model).
* `poll_link_tx(budget)`: the adapter provides **≤ budget** SDUs **ready** to send **for this tick**. Must **return immediately** (non-blocking).
* `on_timer(t_ms)`: drive internal timers (retransmissions, rekey, keepalive…).

> **v1 tolerated option** (runner keeps backward compatibility): `poll_link_tx` may also return `list[tuple[bytes,int]]` (payload, logical time); DryBox doesn’t rely on it and normalizes — prefer **`list[bytes]`**.

### 3.2 SAR-lite (optional on DryBox side)

* **3-byte header**: `{frag_id:u8, idx:u8, last:u8}`.
* Enabled if **`len(SDU) > mtu_bytes`** of the bearer **or** if DryBox decides to force SAR (MTU tests).
* **Reassembly**: keyed by `frag_id`; once `last=1` is received and **all** `idx ∈ [0..last]` are present → deliver to `on_link_rx`.
* **Reassembly timeout** (DryBox side): `2×RTT_est` → silently **abort** the whole fragment set. The adapter **sees nothing** until the SDU is complete.

### 3.3 Size & MTU constraints

* **Before SAR**: `sdu_max_bytes` (capabilities) — recommended 1024.
* **After SAR**: each fragment ≤ bearer `mtu_bytes`.

### 3.4 Delivery semantics

* **Reordering**: possible between SDUs (network) → **do not** assume **in-order** delivery.
* **Duplication**: not modeled in v1 (may be added later).
* **Loss**: modeled by the bearer (IID + burst, Gilbert–Elliott depending on type).

---

## 4) Mode B — AudioBlock (PCM blocks)

### 4.1 API contract

```python
class NadeAudioPort:
    # v1 default: 8 kHz, 20 ms, mono PCM int16 LE
    def pull_tx_block(self) -> "np.ndarray[int16] | None": ...
    def push_rx_block(self, block: "np.ndarray[int16]") -> None: ...
    def on_timer(self, t_ms: int) -> None: ...
```

**Requirements for `pull_tx_block`:**

* Always return a **C-contiguous** `np.ndarray`, dtype **int16**, **mono**, **LE**, length **BLOCK\_SAMPLES** (default 160 @ 8 kHz → 20 ms).
* If silence: return a **zero buffer** (avoid `None`).
* **Never** block.

**Requirements for `push_rx_block`:**

* Reception **after** channel/vocoder/PLC.
* Buffer **C-contiguous int16**, same shape as TX.

> **Parameterization**: sample rate / block size are **fixed** in v1 (8 kHz/20 ms). Announce alternatives via `nade_capabilities().audioparams` (to be stabilized in v2).

### 4.2 Channel/vocoder chain (models)

* DryBox applies **AWGN** or **Rayleigh fading**, then **mock vocoder** (EVS/AMR/Opus NB), optional **VAD/DTX**, **PLC**: hold ≤ 60 ms then attenuation. **CFO/ppm** and the jitter buffer are handled by DryBox (scenario).

---

## 5) Errors, robustness, determinism

* **Exceptions** raised by an adapter in a callback ⇒ DryBox **endpoint error** (**exit code 3**). Log on the adapter side and **fail fast**.
* **No real clock**: don’t `sleep()` and don’t depend on `time.time()` (use incoming `t_ms`).
* **Back-pressure**: `budget` bounds production in Mode A. Keep a **bounded** internal queue and **handle drops** if necessary.
* **Memory**: avoid unnecessary copies; always return **C-contiguous** buffers.

---

## 6) Events & metrics (observability)

### 6.1 Files emitted by DryBox

* `metrics.csv` (fixed columns):  
  `[t_ms, side, layer, event, rtt_ms_est, latency_ms, jitter_ms, loss_rate, reorder_rate, goodput_bps, snr_db_est, ber, per, cfo_hz_est, lock_ratio, hs_time_ms, rekey_ms, aead_fail_cnt]`
* `events.jsonl`: lines of `{"t_ms", "side", "type", "payload"}`
* `capture.dbxcap`: replayable TLV file. Header: `b"DBXC"` (4) + `version=1` (u8); per‑record:  
  `t_ms:u64le | side:u8 (0=L→R,1=R→L) | layer:u8 (0=bytelink,1=bearer) | event:u8 (0=tx,1=rx,2=drop) | len:u32le | data:bytes`

### 6.2 Emitting observability from adapters

Adapters **do not** write metrics directly. Use `ctx.emit_event(type, payload)` to write events. DryBox produces metrics rows at layer boundaries (bearer tx/rx, ByteLink rx, periodic goodput window).
---

## 7) States & scheduling (text)

```
[tick t_ms]
   ├─ L.on_timer(t_ms)
   ├─ R.on_timer(t_ms)
   ├─ if Mode A:
   │     L.poll_link_tx(budget) → enqueue(bearer L→R) [SAR opt.]
   │     R.poll_link_tx(budget) → enqueue(bearer R→L) [SAR opt.]
   │     bearer L→R deliver? → R.on_link_rx(SDU*)
   │     bearer R→L deliver? → L.on_link_rx(SDU*)
   └─ if Mode B:
         L.pull_tx_block() → vocoder/channel → R.push_rx_block()
         R.pull_tx_block() → vocoder/channel → L.push_rx_block()
```

\* SDUs **already reassembled** if SAR is active.

---

## 8) Low-level specifications

### 8.1 PCM (Mode B)

* **Format**: **PCM** **int16** **little-endian**, **mono**, **C-contiguous**.
* **Scale**: −32768..32767 (full scale).
* **Default block**: **20 ms** at **8 kHz** ⇒ **160** samples.

### 8.2 ByteLink (Mode A)

* **SDU**: opaque byte array. **No stream APIs**.
* **Reception**: `on_link_rx` **may be called multiple times** in the same tick (depending on bearer deliveries).
* **Reordering**: adapter **must handle** it (use internal numbering if needed).

### 8.3 SAR-lite

* **Header (3 bytes)**: `frag_id`, `idx`, `last`.
* **Policy**: DryBox **decides** to enable SAR if `len(SDU)>mtu_bytes`.
* **Timeout**: `2×RTT_est` → purge.

---

## 9) Returns & error handling

| Adapter-side situation            | Expected behavior                                  |
| --------------------------------- | -------------------------------------------------- |
| No data to send (Mode A)          | `poll_link_tx` → `[]` immediately                  |
| Silence (Mode B)                  | `pull_tx_block` → zero buffer of the expected size |
| Invalid data (type, dtype, shape) | **Raise** a clear exception → DryBox `exit 3`      |
| Long blocking                     | **Forbidden** (impacts the entire run)             |
| Over-production vs `budget`       | **Do not exceed**; **buffer** reasonably or drop   |

---

## 10) Minimal examples (skeletons)

### 10.1 Mode A (ByteLink)

```python
ABI_VERSION = "1.0"
def nade_capabilities(): return {"abi_version": ABI_VERSION, "bytelink": True, "audioblock": False, "sdu_max_bytes": 1024}

class Adapter:
    def __init__(self, cfg): self.side = cfg["side"]; self.txq = []
    def start(self, ctx): self.ctx = ctx; self.t0 = None
    def on_timer(self, t_ms): 
        if t_ms % 500 == 0: self.txq.append(f"PING {self.side} t={t_ms}".encode())
    def poll_link_tx(self, budget: int): 
        out, self.txq = self.txq[:budget], self.txq[budget:]; return out
    def on_link_rx(self, sdu: bytes): 
        # e.g., parse TLV, drive FSM; emit events
        if b"PONG" in sdu and "metrics" in self.ctx:
            self.ctx["metrics"].event(t_ms=0, side=self.side, type="pong_rx", payload={"len": len(sdu)})
```

### 10.2 Mode B (AudioBlock)

```python
import numpy as np
ABI_VERSION = "1.0"
def nade_capabilities(): return {"abi_version": ABI_VERSION, "bytelink": False, "audioblock": True, "sdu_max_bytes": 1024,
                                 "audioparams": {"sr": 8000, "block": 160}}
class Adapter:
    SR, N = 8000, 160
    def __init__(self, cfg): self.ph = 0.0; self.hz = 1000.0 if cfg["side"]=="left" else 800.0
    def start(self, ctx): self.ctx = ctx
    def on_timer(self, t_ms): pass
    def pull_tx_block(self):
        # Generate a sine (mono, int16, C-contiguous), 20 ms @ 8 kHz
        t = (np.arange(self.N, dtype=np.float32) + self.ph) / self.SR
        self.ph += self.N
        x = 0.2*np.sin(2*np.pi*self.hz*t)
        return (x*32767).astype(np.int16, copy=False)
    def push_rx_block(self, block: np.ndarray): pass
```

---

## 11) Conformance tests (quick checklist)

* **Discovery**: `nade_capabilities()` returns `"abi_version": "1.0"`, and at least one mode.

* **Mode A**:

  * `poll_link_tx(budget)` respects the budget and returns immediately.
  * `on_link_rx` accepts SDUs in **any order**.
  * SDU > MTU: restore **exactly** the source byte-stream after SAR.

* **Mode B**:

  * `pull_tx_block()`: `dtype=int16`, `ndim==1`, `C-contiguous`, **correct length**.
  * `push_rx_block()` accepts the same constraints.

* **Timing**: no method **blocks** (> a few hundred µs).

* **Stability**: 100 runs `seed=0..99` → no exceptions.

* **Metrics/Events**: if the adapter emits (`ctx["metrics"]`), fields are well-formed (UTF-8, JSON-safe).

---

## 12) Exit codes (reminder)

* `0`: OK, thresholds and execution valid.
* `2`: **Acceptance threshold not met** (e.g., missing `handshake_done` / handshake too long).
* `3`: **Endpoint error** (adapter exception, module not found, missing symbol).
* `4`: **Invalid scenario** (YAML, out-of-domain values).

---

## 13) Extensibility & ABI versioning

* **ABI v1.0**: two modes, minimal callbacks, optional SAR-lite, fixed metrics.
* **Forward-compatibility**: new **optional** keys may appear in `nade_capabilities()` and `ctx`.
* **Deprecations**: announced via `abi_version` (e.g., `"1.1"`), with a compatibility period.

---

### TL;DR

* **Mode A**: `on_link_rx(bytes)`, `poll_link_tx(budget)->list[bytes]`, `on_timer(t_ms)`.
* **Mode B**: `pull_tx_block()->np.int16[C]`, `push_rx_block(np.int16[C])`, `on_timer(t_ms)`.
* **PCM**: int16 LE, mono, **20 ms @ 8 kHz** (default).
* **SAR-lite**: 3-byte header `frag_id|idx|last`, timeout `2×RTT_est`.
* **Discovery**: `nade_capabilities()` with `"abi_version": "1.0"`.
* **Non-blocking, single thread, logical `t_ms`**, arrival order not guaranteed in Mode A.
* **Metrics/events** via `ctx["metrics"]` (optional).


### Appendix — Reference mock: PingPong Ed25519 handshake

If `cfg["crypto"]` is present, the PingPong adapter authenticates peers:

- `SYN`: `L_nonce(8) || sig_L("PPv1|SYN|" + L_nonce)`
- `SYNACK`: `R_nonce(8) || sig_R("PPv1|SYNACK|" + L_nonce + R_nonce)`
- `ACK`: `sig_L2("PPv1|ACK|" + L_nonce + R_nonce)`

On success, both sides emit `hs_done` with `{"auth":"ok"}`; otherwise `hs_fail`. A `crypto_info` event logs non‑sensitive key info (pubs, IDs).
