# sample-project

A deliberately imperfect Python project used as repoCity's test bed. It contains, on purpose:

- a circular dependency between `orderbook/core/pricing.py` and `orderbook/core/inventory.py`
- one very high complexity function in `orderbook/core/settlement.py`
- a mix of tidy and untidy modules so every grade appears in the city

Every phase of the roadmap is verified against this tree, so its shape should stay stable.
