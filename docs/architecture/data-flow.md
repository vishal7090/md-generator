# Data Flow

```mermaid
flowchart TD
    Source[Input_source] --> Reader[Reader_or_adapter]
    Reader --> Parsed[Parsed_content_or_metadata]
    Parsed --> Generator[Markdown_generator]
    Generator --> Markdown[Markdown_files]
    Generator --> Diagrams[Mermaid_or_Graphviz_assets]
    Generator --> Zip[ZIP_download_when_API]
```

Data generally flows one way: from input source to generated documentation artifacts. The repository does not define persistent application data stores for the converter services; database and graph modules introspect external systems and write documentation output.
