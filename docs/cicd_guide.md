# CI/CD Pipeline Guide and Troubleshooting

## What is a CI/CD Pipeline?

A CI/CD pipeline is an automated sequence of steps that runs every time code is pushed:
- **CI (Continuous Integration):** build, lint, test
- **CD (Continuous Delivery/Deployment):** package, push to registry, deploy

Pipelines are defined as YAML files checked into the repository.

---

## Pipeline Anatomy

### GitLab CI (.gitlab-ci.yml)

```yaml
stages:
  - build
  - test
  - deploy

build-image:
  stage: build
  script:
    - docker build -t myapp:$CI_COMMIT_SHA .
  only:
    - main

run-tests:
  stage: test
  script:
    - pytest tests/ -v
  artifacts:
    reports:
      junit: test-results.xml

deploy-staging:
  stage: deploy
  script:
    - kubectl set image deployment/myapp app=myapp:$CI_COMMIT_SHA
  environment:
    name: staging
  only:
    - main
```

### GitHub Actions (.github/workflows/deploy.yml)

```yaml
name: CI/CD
on:
  push:
    branches: [main]

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: pytest tests/
      - name: Build Docker image
        run: docker build -t myapp:${{ github.sha }} .
```

---

## How to Troubleshoot a Failed CI/CD Pipeline

### Step 1: Read the Logs

Every pipeline failure leaves logs. They are the most important diagnostic tool.

**GitLab CI:**
- Go to the pipeline → click the failed job → read the full log output.
- The last non-zero exit command is usually the cause.

**GitHub Actions:**
- Click the failed job in the Actions tab → expand the failed step.
- Download the full log with the download button for large outputs.

### Step 2: Identify the Failing Stage

Each pipeline stage fails for different reasons:

| Stage | Common Failure Causes |
|-------|----------------------|
| Build | Compile error, missing dependency, Dockerfile syntax error |
| Test | Test assertion failed, import error, service not reachable |
| Lint | Code style violation, type error |
| Package | Docker daemon not available, registry authentication failed |
| Deploy | kubectl auth failed, image tag not found, resource conflict |

### Step 3: Check Environment Variables and Secrets

Many pipeline failures trace back to a missing or incorrect secret.

```bash
# GitLab: check in Settings > CI/CD > Variables
# GitHub: check in Settings > Secrets and variables > Actions

# In pipeline logs, look for:
# "error: KUBECONFIG not set"
# "unauthorized: authentication required"
# "connection refused" (service URL wrong)
```

**Best practice:** Echo non-secret variables at the start of scripts for debugging:
```yaml
script:
  - echo "Deploying to $DEPLOY_ENV"
  - echo "Image tag: $CI_COMMIT_SHA"
  - kubectl version  # verify auth works before deploy
```

### Step 4: Reproduce Locally

Pull the Docker image used by the runner and run the failing command yourself:

```bash
# GitLab: use the same image as the job
docker run -it python:3.11 bash
# Then run the same commands the pipeline runs

# GitHub Actions: use act (local runner)
act push
```

### Step 5: Check Artifact and Cache Issues

**Artifact errors:** "no files found" — the path in `artifacts: paths:` doesn't match where the file was actually written.

**Cache poisoning:** Old cached dependencies cause test failures.
```yaml
# Force a fresh cache by changing the cache key
cache:
  key: "$CI_COMMIT_REF_SLUG-v2"  # bump the version suffix
  paths:
    - .venv/
```

---

## Common CI/CD Failure Patterns

### Docker Build Failures

```
Step 4/12 : RUN pip install -r requirements.txt
 ---> ERROR: Could not find a version that satisfies the requirement numpy==99.0.0
```

Fix: Pin to valid versions in requirements.txt; use `pip install --no-cache-dir` to avoid stale caches.

### Test Failures Due to Missing Services

Tests that need a database or message queue fail because the service isn't running.

**GitLab fix (services block):**
```yaml
test:
  services:
    - postgres:15
  variables:
    POSTGRES_DB: testdb
    POSTGRES_USER: user
    POSTGRES_PASSWORD: pass
  script:
    - pytest tests/
```

**GitHub Actions fix:**
```yaml
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_PASSWORD: postgres
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
```

### Deployment Fails with 401/403

```
Error from server (Forbidden): deployments.apps "myapp" is forbidden
```

The service account used by the pipeline doesn't have permission.

Fix: Bind the appropriate ClusterRole to the pipeline's service account:
```bash
kubectl create rolebinding pipeline-deployer \
  --clusterrole=edit \
  --serviceaccount=default:pipeline-sa \
  --namespace=production
```

---

## Environment Variable Best Practices

1. Never hardcode secrets in `.gitlab-ci.yml` or `.github/workflows/` files.
2. Use masked variables for secrets (GitLab) or encrypted secrets (GitHub).
3. Use environment-specific variables: `$PROD_DB_HOST` vs `$STAGING_DB_HOST`.
4. Reference variables consistently: `$VAR_NAME` (bash), `${{ secrets.VAR }}` (GitHub Actions).

---

## Pipeline Optimization

- **Parallelism:** Run independent jobs in parallel stages.
- **Caching:** Cache `node_modules/`, `.venv/`, `.m2/` to skip reinstallation.
- **Selective runs:** Use `only/except` (GitLab) or `paths` filters (GitHub) to skip pipelines for doc-only changes.
- **Artifacts:** Pass build outputs between stages using artifacts to avoid rebuilding.
