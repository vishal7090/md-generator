# Architecture Overview

`mdengine` is a modular Python monorepo with one installable distribution and many optional runtime surfaces.

```mermaid
flowchart TB
    subgraph packageLayer[Python_distribution]
        Engine[mdengine_package]
        Modules[md_generator_modules]
        Extras[optional_dependency_extras]
    end
    subgraph interfaceLayer[Interfaces]
        CLI[CLI_entry_points]
        API[FastAPI_apps]
        MCP[MCP_servers]
    end
    subgraph runtimeLayer[Runtime_targets]
        Local[Local_terminal]
        Docker[Docker_compose_gateway]
        CI[GitHub_Actions]
    end
    CLI --> Modules
    API --> Modules
    MCP --> Modules
    Engine --> Modules
    Extras --> Modules
    Local --> CLI
    Docker --> API
    CI --> Engine
```

The dominant pattern is a modular monolith. Feature areas share packaging, test configuration, and release cadence while keeping converter logic in separate modules.
