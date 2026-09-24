# Vendored wheels (CI)

Pinned public packages for hermetic CI (also installable from PyPI).

| Wheel | Purpose |
|-------|---------|
| `kazen_event_schema-0.6.1-py3-none-any.whl` | Event schema (`pip install kazen-event-schema==0.6.1`) |
| `kazenai-1.0.2-py3-none-any.whl` | Core SDK (`pip install kazenai==1.0.2`) |
| `kazenai_finops-1.0.2-py3-none-any.whl` | FinOps SDK (`pip install kazenai-finops==1.0.2`) |
| `kazenai_contracts-0.1.0-py3-none-any.whl` | Contracts (not on PyPI) |

Refresh:

```bash
pip download --no-deps -d vendor kazenai==1.0.2 kazen-event-schema==0.6.1 kazenai-finops==1.0.2
# contracts still from sibling build under ../kazenai-contracts
```
