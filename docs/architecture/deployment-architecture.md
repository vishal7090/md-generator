# Deployment Architecture

The checked-in deployment stack is Docker Compose plus nginx. The compose file currently runs the gateway and selected converter APIs: ZIP, image, text, Word, PDF, PPT, and XLSX.

```mermaid
flowchart LR
    Browser[Browser_or_HTTP_client] --> Nginx[Nginx_on_8080]
    Nginx --> Zip[zip_to_md_API]
    Nginx --> Image[image_to_md_API]
    Nginx --> Text[text_json_xml_API]
    Nginx --> Word[word_to_md_API]
    Nginx --> Pdf[pdf_to_md_API]
    Nginx --> Ppt[ppt_to_md_API]
    Nginx --> Xlsx[xlsx_to_md_API]
```

Run it from the repository root:

```bash
docker compose -f deploy/docker-compose.yml up --build
```
