# LMU AI Race Engineer

[日本語版はこちら](README.md)

An AI-powered race engineer that reads live telemetry and delivers radio-style instructions to the driver.  
Runs locally with Le Mans Ultimate + LM Studio (local LLM). No cloud required.

<!-- Add demo GIF here -->

---

## Overview

Reads telemetry directly from the rFactor 2 shared memory (`rFactor2SharedMemoryMapPlugin64.dll`) and sends it to a locally running LLM (LM Studio) to generate short, realistic engineer radio messages.

**SimHub is not required.** The plugin bundled with LMU already writes all game state to shared memory.

### Available telemetry data

- Speed, gear, RPM, fuel
- Tyre wear / temperature / pressure / compound (all 4 wheels)
- Gap to car ahead, gap to car behind, gap to leader
- Remaining race time and remaining laps
- Weather (rain intensity, air temp, track temp, wind speed)
- Body damage, detached parts, overheat warning
- ERS battery level and motor temperature
- Sector times and best lap

### Personas

- **2 personas** — Professional engineer / Cheerful girl engineer "Ai"
- Japanese / English output
- Fully local (no internet connection needed)

---

## Requirements

| Software | Purpose |
|---|---|
| [Le Mans Ultimate](https://www.lemansultimate.com/) | Racing sim (rF2 SharedMemory plugin included) |
| [LM Studio](https://lmstudio.ai/) | Local LLM server |
| Python 3.9+ | Script runtime |

> **SimHub is not needed.** The `rFactor2SharedMemoryMapPlugin64.dll` bundled with LMU handles shared memory output automatically.

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/akisakurap/LMU-AI.git
cd LMU-AI
```

### 2. Install dependencies

```bash
pip install openai
```

`mmap` and `ctypes` are part of the Python standard library — no additional packages needed.

### 3. Verify the LMU SharedMemory plugin

`rFactor2SharedMemoryMapPlugin64.dll` is installed in `<LMU>\Plugins\` as part of the LMU installation. No extra steps required.

### 4. Start a model in LM Studio

1. Load a model in LM Studio (e.g. `google/gemma-4-e2b`)
2. Open the **Local Server** tab and click **Start Server** (default port: `1234`)

> **Tip:** If using a reasoning/thinking model, consider increasing `max_tokens` (default: 1500).

### 5. Edit configuration

Edit the variables at the top of `race_engineer.py` to match your setup:

```python
LANGUAGE   = 'en'                   # 'ja' (Japanese) or 'en' (English)
PERSONA    = 'default'              # 'default' (pro engineer) or 'girl' (Ai)
MODEL_NAME = 'google/gemma-4-e2b'  # Exact model name as shown in LM Studio
```

---

## Usage

Start LMU and enter a session, then run:

```bash
python race_engineer.py
```

The engineer will read telemetry and call the LLM every `INTERVAL_SEC` seconds (default: 10).  
Press `Ctrl+C` to stop.

### Sample output (default persona)

```
============================================================
  Race Engineer — LMU + rF2 SharedMemory + LM Studio
  Persona: default | Language: en | Model: google/gemma-4-e2b
  LLM call: every 10s
  Press Ctrl+C to stop.
============================================================
[2026-05-06 15:23:01] Lap 12 | 245 km/h | Fuel: 42.3L | P3/20
  Gap: +1.234s / -0.876s | Leader: 8.5s
------------------------------------------------------------
[ENGINEER] Front-right tyre temp is a bit high. Try braking slightly earlier into Turn 3. Fuel looks fine, carry on.
============================================================
```

### Sample output (girl persona)

```
============================================================
[2026-05-06 15:23:01] Lap 12 | 245 km/h | Fuel: 42.3L | P3/20
  Gap: +1.234s / -0.876s | Leader: 8.5s
------------------------------------------------------------
[ENGINEER] Your front-right tyre is running a bit hot! Try braking a little earlier next lap. Fuel's totally fine — you got this!
============================================================
```

---

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `LANGUAGE` | `'ja'` | Output language. `'ja'` (Japanese) or `'en'` (English) |
| `PERSONA` | `'default'` | AI persona. `'default'` (professional) or `'girl'` (Ai) |
| `MODEL_NAME` | `'google/gemma-4-e2b'` | Exact model name loaded in LM Studio |
| `INTERVAL_SEC` | `10` | Seconds between LLM calls |
| `LLM_TIMEOUT` | `30` | LLM call timeout in seconds |
| `LM_STUDIO_URL` | `http://localhost:1234/v1` | LM Studio base URL |

---

## Screenshot

<!-- Add screenshot here -->

---

## License

MIT
