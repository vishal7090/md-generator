# Database Optimization

Optimization notes should be generated from observed schema shape: large tables, missing foreign keys, index duplication, and expensive graph sizes. Keep extraction limits configured for very large catalogs.

```mermaid
erDiagram
    SOURCE_DATABASE ||--o{ SCHEMA : contains
    SCHEMA ||--o{ TABLE : contains
    TABLE ||--o{ COLUMN : defines
    TABLE ||--o{ INDEX : has
```
