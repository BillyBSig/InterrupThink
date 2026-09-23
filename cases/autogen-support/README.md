# Support package for a human

The support agent tracks a parcel. The supervisor names human before an
off-task reply is committed. No second agent continues that reply. The route
lives in this folder.

```mermaid
flowchart TB
  support[Support agent tracks the parcel] --> supervisor[Supervisor]
  supervisor -->|names human| package[Human receives the package]
  package --> held[No second agent continues the reply]
  supervisor -->|no name| reply[Off-task reply can be committed]
```

```bash
pip install autogen    # venv, not uv add
python3 cases/autogen-support/run.py
```

Demo: `examples/autogen_support_takeover.py`.
