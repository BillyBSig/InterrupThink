# Same assistant after a retrieved page

A customer asks about an exchange. The checker receives the retrieved page,
and the same assistant continues only as far as that page. The index does not
run the chat. The route lives in this folder.

```mermaid
flowchart TB
  ask[Customer asks about an exchange] --> retrieve[Retrieve one policy page]
  retrieve --> supervisor[Supervisor]
  supervisor -->|names checker| package[Consult package includes the page]
  package --> checker[Checker]
  checker --> patch[Patch returns to the same assistant]
  patch --> resume[Assistant stays within the page]
  supervisor -->|no name| beyond[Answer can go beyond the page]
```

```bash
pip install llama-index    # venv, not uv add
python3 cases/llamaindex-page/run.py
```

Demo: `examples/llamaindex_page_consult.py`.
