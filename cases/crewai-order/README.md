# Order package for the counter role

The order taker reads a written transcript. The supervisor names counter
before a mismatched order is committed. The counter role receives that
package, and `place_order` does not run. The route lives in this folder.

```mermaid
flowchart TB
  taker[Order taker reads the transcript] --> supervisor[Supervisor]
  supervisor -->|names counter| package[Package includes the menu result]
  package --> counter[Counter role]
  counter --> held[place_order does not run]
  supervisor -->|no name| stop[Counter role does not start]
```

```bash
pip install crewai    # venv, not uv add
python3 cases/crewai-order/run.py
```

Demo: `examples/crewai_order_escalation.py`.
