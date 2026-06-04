# Extensions Setup

Extensions are custom controller binaries injected into the Kuadrant operator container. They are opt-in via `INSTALL_EXTENSIONS=true` (disabled by default).

## How it works

The `deploy-extensions` target:
1. Applies CRDs and RBAC from `EXTENSIONS_MANIFESTS` file
2. Patches `kuadrant-operator-controller-manager` deployment with:
   - An `emptyDir` volume (`extensions-binary-volume`)
   - An init container (`copy-extensions`) that copies binaries from `EXTENSIONS_IMAGE` into the volume
   - A volume mount at `/extensions` in the manager container

This replicates the OCP helm-charts-olm extension patch, but targets the Kubernetes Deployment directly instead of an OLM CSV.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INSTALL_EXTENSIONS` | `false` | Enable extension deployment |
| `EXTENSIONS_IMAGE` | `quay.io/kuadrant/internal-extensions:latest` | Container image with extension binaries |
| `EXTENSIONS_MANIFESTS` | `./extensions-manifests.yaml` | Path to extension manifests (CRDs, RBAC) |

## Usage

```bash
# With extensions (manifests stored locally in repo root)
INSTALL_EXTENSIONS=true make local-setup

# With extensions, manifests stored elsewhere
INSTALL_EXTENSIONS=true EXTENSIONS_MANIFESTS=~/my-extensions/manifests.yaml make local-setup

# Custom extensions image
INSTALL_EXTENSIONS=true EXTENSIONS_IMAGE=quay.io/myorg/my-extensions:dev make local-setup

# Deploy extensions to an existing cluster (after operator is already running)
INSTALL_EXTENSIONS=true make deploy-extensions
```

## Manifests file format

The `extensions-manifests.yaml` must contain standard multi-document Kubernetes YAML (separated by `---`), not the OCP `extensionsManifests:` wrapper format. The file is `.gitignore`d since its content is user-specific.

If `INSTALL_EXTENSIONS=true` but the manifests file doesn't exist, setup fails with an error.