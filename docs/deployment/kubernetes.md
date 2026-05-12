# Kubernetes Deployment

No Kubernetes manifests were detected in the repository. A production Kubernetes deployment should translate each API container into a Deployment, expose services through an Ingress, and externalize upload limits, timeout settings, and workspace storage.

## Recommended Baseline

- One Deployment per converter API that must scale independently.
- Readiness probes against `/health` where implemented or FastAPI docs/OpenAPI endpoints where safe.
- Persistent or object storage for large asynchronous artifacts if pods are ephemeral.
- Ingress authentication and upload limits.
