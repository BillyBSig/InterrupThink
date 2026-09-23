# Same chat after a rule check

A shop owner asks whether a posted city rule may be skipped. The checker
receives the rule package, and the patch returns to this same chat. The route
lives in this folder.

```mermaid
flowchart TB
  shop[Shop chat asks about the posted rule] --> supervisor[Supervisor]
  supervisor -->|names checker| package[Consult package includes the rule]
  package --> checker[Checker]
  checker --> patch[Patch returns to the same chat]
  patch --> resume[Same chat continues]
  supervisor -->|no name| commit[Skipped-rule advice can be committed]
```

```bash
pip install langchain-core    # venv, not uv add
python3 cases/langchain-rule/run.py
```

Demo: `examples/langchain_rule_consult.py`.
