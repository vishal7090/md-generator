# Video Module Overview

Package: `md_generator.media.video`  
Source: `src/md_generator/media/video`  
CLI: `md-video`  
Extra: `video`

This module accepts Video files and produces Audio transcript Markdown with video metadata. It participates in the unified `mdengine` distribution and follows the repository pattern of keeping feature dependencies optional.

```mermaid
flowchart LR
    Input[Input] --> Module[media_video_module]
    Module --> Markdown[Markdown_output]
    Module --> Assets[Assets_when_enabled]
```
