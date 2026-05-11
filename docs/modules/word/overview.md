# Word Module Overview

Package: `md_generator.word`  
Source: `src/md_generator/word`  
CLI: `md-word`  
Extra: `word`

This module accepts DOCX documents and produces Markdown with optional image extraction. It participates in the unified `mdengine` distribution and follows the repository pattern of keeping feature dependencies optional.

```mermaid
flowchart LR
    Input[Input] --> Module[word_module]
    Module --> Markdown[Markdown_output]
    Module --> Assets[Assets_when_enabled]
```
