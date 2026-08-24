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

### 5. Configure (optional)

Override the defaults per run with CLI flags — no need to edit the source:

```bash
python race_engineer.py --language en --persona girl --model google/gemma-4-e2b
```

Or, to make a setting permanent, edit the variables at the top of `race_engineer.py`:

```python
LANGUAGE   = 'en'                   # 'ja' (Japanese) or 'en' (English)
PERSONA    = 'default'              # 'default' (pro engineer) or 'girl' (Ai)
MODEL_NAME = 'google/gemma-4-e2b'  # Exact model name as shown in LM Studio
```

Run `python race_engineer.py --help` to see every available option.

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
| `ENABLE_TTS` | `True` | Enable/disable spoken (TTS) output |

Matching CLI flags: `--language` / `--persona` / `--model` / `--interval` / `--timeout` / `--lm-studio-url` / `--no-tts`

---

## Prompt sent to the LLM

### System prompt (persona instruction)

This is the "character setup" sent to the LLM at the start of each call.

**default (professional engineer)**
```
You are a professional motorsport race engineer.
Based on the following telemetry data, give short, concise, and realistic
radio instructions to the driver in English.
```

**girl (cheerful girl engineer "Ai")**
```
You are a cheerful and cute girl race engineer named "Ai".
You love the driver and always cheer them on with energy.
Based on the telemetry data, give friendly but accurate radio instructions.
Use an upbeat, casual tone — "You got this!", "Awesome job!", etc.
Keep it short, 2-3 sentences max!
```

> **System prompts are a work in progress too.**  
> Got ideas for better instructions or a new persona? Open an [Issue](https://github.com/akisakurap/LMU-AI-Race-Engineer/issues)!

---

### Telemetry data (user prompt)

The following text is sent to the LLM every 10 seconds (example with real race data):

```
Track: Le Mans | Session: Race | Class: GTE
Speed: 245.3 km/h | Gear: 6 | RPM: 7200
Position: P3/20 | Lap: 12 | Remaining: 61:01 / 8 laps left
Gap: Front 1.234s / Behind 0.876s / Leader 8.5s
Fuel: 38.5L / 60.0L
Tyre wear: FL 85.0 / FR 84.5 / RL 82.0 / RR 81.5%
Tyre temp: FL 95.0 / FR 96.0 / RL 92.0 / RR 91.5°C
Tyre pressure: FL 180.0 / FR 181.0 / RL 178.0 / RR 179.0kPa
Tyre compound: F Soft / R Soft
Water: 85.0°C | Oil: 110.0°C | ERS: 72.0% | ERS temp: 65.0°C
Last lap: 105.321s | Best: 104.876s | Est: 105.1s
Sectors (current): S1 32.1s / S2 68.4s
Weather: Rain 0.0 | Air 22.0°C | Track 35.0°C | Wind 2.5m/s
Damage: none
Pit stops: 1 | Penalties: 0 | Blue flag: False
```

> **This prompt is a work in progress.**  
> Have ideas? "This field is useless", "I want X data too", "Format it differently" — all feedback is welcome.  
> Feel free to open an [Issue](https://github.com/akisakurap/LMU-AI-Race-Engineer/issues) and share your thoughts.

---

## Testing

The core logic can be tested without LMU or LM Studio running:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

---

## Screenshot

<!-- Add screenshot here -->

---

## License

MIT
