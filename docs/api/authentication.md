# Authentication

No repository-level authentication middleware, OAuth flow, API key dependency, or Django/Flask authentication layer was detected in the FastAPI applications.

## Deployment Guidance

For production deployments, put authentication at the platform edge:

- API gateway or reverse proxy authentication.
- OAuth2/OIDC through an ingress controller or identity-aware proxy.
- Network allowlists for internal conversion services.
- Short-lived signed URLs or authenticated storage for generated artifacts.

Do not expose conversion APIs directly to the internet without upload limits, authentication, malware scanning controls, and rate limiting.
