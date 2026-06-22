<img width="2400" height="600" alt="hero-b" src="https://github.com/user-attachments/assets/4005eb1b-539d-4d35-9683-3a61ec9d9301" />

# Sea Traces Python SDK

[![MIT License](https://img.shields.io/badge/License-MIT-red.svg?style=flat-square)](https://opensource.org/licenses/MIT)

## Installation

```
pip install sea-traces
```

## Usage

```python
from sea_traces import SeaTraces

client = SeaTraces()
```

Configure the SDK with:

```bash
SEA_TEAM_KEY=sea-team-key
SEA_TRACES_BASE_URL=https://your-sea-traces.example.com
```

The legacy `langfuse` import path remains available for compatibility, but
`SEA_TEAM_KEY` and `SEA_TRACES_BASE_URL` are required for SDK initialization.
