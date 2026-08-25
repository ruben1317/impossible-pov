# Architecture — V1.1

## Pipeline

```text
Next.js UI
   ↓
FastAPI approval endpoints
   ↓
WorkflowService
   ├── ProviderRegistry
   │    ├── TextProvider
   │    ├── ResearchProvider
   │    ├── VideoProvider
   │    ├── VoiceProvider
   │    ├── Renderer
   │    └── Publisher
   ├── BudgetService
   └── StorageProvider
        ↓
SQLite / local media storage
```

## Design rules

1. No API key in YAML or source code.
2. Models and provider-specific options are configuration, not workflow logic.
3. Research is independent from text generation so it can later move to a web-grounded provider.
4. Paid generation must pass the budget check first.
5. Every project remains approval-gated.
6. Generated media is stored by project, not as opaque temporary URLs only.
7. YouTube is the sole publisher in this repo.

## Provider registry

`backend/app/providers/registry.py` maps configured stage names to provider adapters. Switching a stage from mock to live should require only a config change plus the corresponding secret.

## Cost ledger

`GenerationCost` stores provider, operation, scene index, estimated cost, actual cost, and timestamp. It supports monthly spend reporting and hard-stop enforcement.

## Storage

`LocalStorage` is implemented. Future S3/R2 storage should implement the same project/path behavior and be selected through config.

## Next engineering milestone

Implement Runway as an asynchronous job provider with create/poll/download methods. Store its provider job ID, output file path, and actual cost per scene. Then add per-scene regeneration without re-rendering approved scenes.

## V1.2 Mobile configuration layer

Everyday settings no longer require editing `config/app.yaml`. The backend stores UI overrides in the `RuntimeSetting` table and deep-merges them on top of the checked-in baseline config for each request. Secrets remain environment variables and are never returned by the public API.

The frontend is designed as an installable mobile web app. After cloud deployment, the normal operating loop is Create → Review → Approve from the user's phone while servers perform generation, rendering, storage, and publishing.
