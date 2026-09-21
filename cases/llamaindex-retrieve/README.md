# Retrieve with LlamaIndex, then check before acting

This example assumes an application already has a LlamaIndex
`VectorStoreIndex`. LlamaIndex performs retrieval with
`index.as_retriever().retrieve(query)`, and the retrieved text is passed into
an InterrupThink session.

The important separation is simple: LlamaIndex finds information, while
`run_session` checks the specialist's reasoning before a later file write.
This example is not a chat application and does not add a vector database or a
retriever to the InterrupThink package.

The policy fixtures are shared with `cases/two-specialists/`.

```bash
pip install llama-index llama-index-llms-openai llama-index-embeddings-openai
python3 cases/llamaindex-retrieve/run.py   # personal .env
```

Demo: `examples/llamaindex_retrieve_node.py`.
