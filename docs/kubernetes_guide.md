# Kubernetes Concepts and Troubleshooting Guide

## Pod Lifecycle and States

A Pod moves through these phases:
- **Pending** — scheduled but containers not yet started (pulling image, waiting for node resources)
- **Running** — at least one container is running
- **Succeeded** — all containers exited with code 0 (for Jobs)
- **Failed** — all containers have stopped; at least one exited with non-zero code
- **Unknown** — node lost communication with the API server

```bash
kubectl get pods                          # overview
kubectl get pods -n <namespace>           # specific namespace
kubectl describe pod <pod-name>           # full event and status details
kubectl logs <pod-name>                   # logs of the main container
kubectl logs <pod-name> -c <container>    # specific container in multi-container pod
kubectl logs <pod-name> --previous        # logs of the previous (crashed) instance
```

---

## CrashLoopBackOff

**What it means:** Kubernetes tried to start the container, it crashed (non-zero exit code), restarted it, it crashed again — repeatedly. Kubernetes adds exponential backoff between restarts (10s, 20s, 40s... up to 5 minutes).

### Common Causes

**1. Application crash on startup**
- Missing required environment variable
- Can't connect to database or dependency
- Configuration file missing or invalid

**2. OOMKilled (Out of Memory)**
- Container exceeded its memory limit
- Check: `kubectl describe pod <name>` and look for `OOMKilled: true`

**3. Liveness probe failure**
- The liveness probe marks the container unhealthy before the app is ready
- Kubernetes kills and restarts it → CrashLoopBackOff
- Fix: increase `initialDelaySeconds` on the liveness probe

**4. Wrong or missing entrypoint**
- The command/args in the Pod spec points to a binary that doesn't exist (exit 127)

### How to Debug CrashLoopBackOff

```bash
# Step 1: See why it crashed
kubectl logs <pod-name> --previous

# Step 2: Full event history
kubectl describe pod <pod-name>
# Look at: Events section (ImagePullBackOff, OOMKilled, Error, etc.)
# Look at: Last State: exit code

# Step 3: Check resource pressure
kubectl top nodes
kubectl top pods

# Step 4: If you need to inspect the container interactively
# Override the command to prevent immediate crash:
kubectl run debug-pod --image=<same-image> --command -- sleep 3600
kubectl exec -it debug-pod -- /bin/sh
```

---

## Common Pod Status Issues

### ImagePullBackOff / ErrImagePull

**Cause:** Kubernetes can't pull the container image.

```bash
kubectl describe pod <pod-name>
# Look for: Failed to pull image... 401 Unauthorized  or  not found
```

**Fix:**
- Wrong image name or tag → fix the Deployment spec
- Private registry → create a Kubernetes secret:
  ```bash
  kubectl create secret docker-registry regcred \
    --docker-server=myregistry.example.com \
    --docker-username=myuser \
    --docker-password=mypassword
  ```
  Then add `imagePullSecrets: [{name: regcred}]` to the Pod spec.

### Pending Pod (Not Scheduling)

**Cause:** No node has enough resources, or constraints can't be satisfied.

```bash
kubectl describe pod <pod-name>
# Events: "0/3 nodes are available: insufficient memory" 
#         "node(s) had untolerated taint"
#         "no persistent volumes available"
```

**Fix:**
- Scale up nodes or reduce resource requests in the Pod spec.
- Check node taints: `kubectl get nodes -o json | jq '.items[].spec.taints'`
- Check PVC status: `kubectl get pvc`

---

## Deployment Rollout Strategies

### RollingUpdate (Default)

Replaces old pods incrementally. Zero downtime for stateless apps.

```yaml
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1    # how many pods can be down during update
      maxSurge: 1          # how many extra pods can be created above desired count
```

Key: at any point during rollout, at least `replicas - maxUnavailable` pods are serving traffic.

```bash
# Watch the rollout
kubectl rollout status deployment/<name>

# Pause a rollout (canary testing)
kubectl rollout pause deployment/<name>

# Roll back to previous version
kubectl rollout undo deployment/<name>

# Roll back to a specific revision
kubectl rollout history deployment/<name>
kubectl rollout undo deployment/<name> --to-revision=2
```

### Recreate Strategy

Terminates all old pods before starting new ones. Causes downtime. Use only for stateful apps where two versions can't run simultaneously.

```yaml
spec:
  strategy:
    type: Recreate
```

---

## Resource Requests and Limits

```yaml
resources:
  requests:          # minimum guaranteed; used for scheduling
    memory: "128Mi"
    cpu: "250m"      # 250 millicores = 0.25 CPU core
  limits:            # maximum allowed; exceeding causes OOMKill or CPU throttle
    memory: "256Mi"
    cpu: "500m"
```

**Rules:**
- CPU limit exceeded → container is throttled (slowed), not killed.
- Memory limit exceeded → container is OOMKilled (exit code 137).
- No requests set → pod may be evicted first under node pressure (BestEffort QoS).

---

## Liveness and Readiness Probes

**Liveness probe:** Is the container still healthy? Failure → kill and restart the container.
**Readiness probe:** Is the container ready to serve traffic? Failure → remove from Service endpoints.

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 30   # wait 30s before first check (give app time to start)
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

**Common mistake:** Setting `initialDelaySeconds` too low causes CrashLoopBackOff for slow-starting apps.

---

## Service Troubleshooting

**Symptom:** Pod is running but traffic can't reach it.

```bash
# Check Service exists and has endpoints
kubectl get svc <service-name>
kubectl describe svc <service-name>
# If "Endpoints: <none>" — the selector isn't matching any pods

# Verify pod labels match service selector
kubectl get pods --show-labels
kubectl get svc <service-name> -o yaml | grep selector

# Test from inside the cluster
kubectl run curl-test --image=curlimages/curl --rm -it -- \
  curl http://<service-name>.<namespace>.svc.cluster.local
```

---

## Useful kubectl Commands

```bash
kubectl get all -n <namespace>
kubectl get events --sort-by='.lastTimestamp'
kubectl exec -it <pod-name> -- /bin/bash
kubectl cp <pod-name>:/path/to/file ./local-file
kubectl port-forward svc/<service> 8080:80
kubectl scale deployment/<name> --replicas=3
kubectl delete pod <pod-name>   # triggers recreation by the ReplicaSet
```
