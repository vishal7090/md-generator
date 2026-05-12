# Database Migrations

No Alembic or Django migration tree was detected for application-owned persistence. For documented databases, migration history remains in the source database or the owning application repository.

```mermaid
erDiagram
    SOURCE_DATABASE ||--o{ SCHEMA : contains
    SCHEMA ||--o{ TABLE : contains
    TABLE ||--o{ COLUMN : defines
    TABLE ||--o{ INDEX : has
```
