# Database Indexing

The DB exporter can document detected indexes from source databases. Use generated index pages to review uniqueness, coverage, naming consistency, and candidates for query optimization.

```mermaid
erDiagram
    SOURCE_DATABASE ||--o{ SCHEMA : contains
    SCHEMA ||--o{ TABLE : contains
    TABLE ||--o{ COLUMN : defines
    TABLE ||--o{ INDEX : has
```
