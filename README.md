# App repo — código, contenedores, CI/CD y manifiestos GitOps

Este es el **repositorio de la aplicación** (código + CI + manifiestos de despliegue). Es la
**fuente de verdad** que ArgoCD observa. 

## Componentes

| Capa | Tecnología | Puerto | Imagen |
|------|------------|--------|--------|
| Frontend | Nginx (no-root, uid 101) sirve HTML estático y hace reverse-proxy de `/api/*` | 8080 | `svillegas/reto-frontend` |
| Backend | FastAPI + Uvicorn (no-root, uid 10001) | 8000 | `svillegas/reto-backend` |

### Endpoints del backend

- `GET /api/health` — liveness/readiness (`{"status":"ok"}`)
- `GET /api/info` — metadatos de build/runtime (versión, git_sha, hostname)
- `GET /api/message` — endpoint de negocio que renderiza el frontend
- `GET /api/docs` — Swagger UI

## Dockerfiles multi-stage

Ambos usan dos etapas para mantener imágenes pequeñas y sin herramientas de build en runtime:

- **Backend:** etapa `builder` instala dependencias en un virtualenv; la etapa `runtime`
  (python:3.12-slim) copia solo el venv + código y corre como uid 10001. Recibe
  `GIT_SHA`/`APP_VERSION` por `--build-arg`.
- **Frontend:** etapa `builder` (alpine) pre-comprime assets con gzip; la etapa `runtime` usa
  `nginx-unprivileged` (no-root, 8080) y copia solo los assets.

Build local (opcional):

```bash
docker build -t svillegas/reto-backend:dev  --build-arg GIT_SHA=$(git rev-parse HEAD) backend
docker build -t svillegas/reto-frontend:dev frontend
```

## GitFlow

Modelo de ramas adoptado:

```
feature/*  ──PR──▶ develop  ──PR──▶ release/*  ──PR──▶ main
                      ▲                              │
                      └────────── back-merge ────────┤
                                                hotfix/* ──PR──▶ main (+ back-merge a develop)
```

- `develop`, `release/*` y `main` **solo se actualizan vía Pull Request** (sin push directo).
- `feature/*` salen de `develop` y vuelven a `develop` por PR.
- `release/*` sale de `develop`; estabiliza y se integra a `main` por PR (+ back-merge a `develop`).
- `hotfix/*` sale de `main`; corrige y se integra a `main` por PR (+ back-merge a `develop`).

### Protección de ramas (configurar en GitHub)

En **Settings → Rulesets** para `develop`, `main` y el patrón `release/*`:

- ✅ **Require a pull request before merging** (sin push directo).
- ✅ **Require status checks to pass** → seleccionar el check del pipeline de validación.
- ✅ **Require branches to be up to date before merging**.
- ✅ (recomendado) **Require linear history** y revisión de al menos 1 aprobador.

## Dos entornos en el mismo clúster (Kustomize)

`develop → staging` y `main → prod`, en **namespaces distintos** del mismo clúster, sin Helm ni
duplicación de manifiestos: una `base` + dos `overlays` de **Kustomize**.

```
k8s/
  base/                       # común: Deployments + Services (sin namespace, imagen sin tag)
    kustomization.yaml
  overlays/
    staging/                  # namespace reto-app-staging, replicas 1, nodePort 30080
      kustomization.yaml
      namespace.yaml
    prod/                     # namespace reto-app-prod, replicas 2, nodePort 30081
      kustomization.yaml
      namespace.yaml
```

Diferencias por entorno (en el `kustomization.yaml` del overlay): `namespace`, número de `replicas`,
`nodePort` del frontend (30080 staging / 30081 prod para evitar colisión), y el **tag de imagen**
(campo `images:`).

Validación local:

```bash
kustomize build k8s/overlays/staging   # o: kubectl kustomize k8s/overlays/staging
kustomize build k8s/overlays/prod
kustomize build k8s/overlays/staging | kubeconform -strict -summary -schema-location default
```

El **tag de imagen** lo gestiona el pipeline vía `kustomize edit set image` sobre el overlay
correspondiente (no editar a mano); luego auto-commitea y ArgoCD sincroniza (pull-based).

## ArgoCD (GitOps pull-based)

Hay **una `Application` de ArgoCD por entorno** — definidas y aprovisionadas **en el repo de
infraestructura** (Terraform), no aquí:

| Application | targetRevision | path | namespace |
|-------------|----------------|------|-----------|
| `reto-app-staging` | `develop` | `k8s/overlays/staging` | `reto-app-staging` |
| `reto-app-prod`    | `main`     | `k8s/overlays/prod`    | `reto-app-prod`    |

Cada una usa `automated` (prune + selfHeal) y `CreateNamespace=true`.

## Pipeline CI/CD (`azure-pipelines.yml`)

Separa **validación (PR)** de **entrega (push a rama de larga duración)**:

### En Pull Request (validación, SIN efectos)

Disparado por `pr:` (a `develop` / `main` / `release/*`). Corre, sin tocar registry ni Git:

1. **SecretScan** — Gitleaks.
2. **SCA** — Trivy fs (falla en HIGH/CRITICAL).
3. **ManifestValidation** — `kustomize build` de ambos overlays + `kubeconform`.
4. **BuildAndScan** — build multi-stage + Trivy image (gate de calidad).

### En push a `develop` → STAGING (entrega)

Validación completa **+**:

5. **DeployStaging** — `docker push` (tag = SHA del commit) → `kustomize edit set image` en
   `overlays/staging` → commit `[skip ci]` a `develop`. ArgoCD `reto-app-staging` sincroniza.

### En push a `main` → PROD (promoción, SIN rebuild)

6. **PromoteProd** — **no reconstruye**: lee el tag ya validado en `overlays/staging` y lo fija en
   `overlays/prod` (`kustomize edit set image`) → commit `[skip ci]` a `main`. ArgoCD
   `reto-app-prod` sincroniza. Prod corre exactamente los mismos bits probados en staging.

Inmutabilidad: las imágenes se etiquetan con el **SHA completo del commit**.
Anti-bucle: el path-filter excluye `k8s/overlays/*` y los auto-commits llevan `[skip ci]`.

**Variables secretas requeridas en Azure DevOps:** `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`. El
Build Service necesita permiso de *Contribute* (o un PAT) para hacer push de los auto-commits.

## Seguridad de los workloads

Definida en los Deployments de `k8s/base`: `runAsNonRoot`, `readOnlyRootFilesystem: true` (con
`emptyDir` para `/tmp` y caché de Nginx), `allowPrivilegeEscalation: false`, `capabilities.drop:
[ALL]`, `seccompProfile: RuntimeDefault`. Cada namespace de entorno fuerza el Pod Security Standard
**restricted**.
