# Docker Troubleshooting Guide

## Why is My Container Failing to Start?

When a Docker container fails to start, it exits immediately after launch. The most important first step is always to read the container logs:

```bash
docker logs <container_name_or_id>
docker logs --tail 50 <container_name>   # last 50 lines
docker logs -f <container_name>          # follow live output
```

### Understanding Exit Codes

The exit code tells you the category of failure:

| Exit Code | Meaning | Common Causes |
|-----------|---------|---------------|
| 0 | Success | Container completed its task |
| 1 | Application error | App crashed, uncaught exception |
| 125 | Docker daemon error | Docker itself failed to run the container |
| 126 | Permission denied | Entrypoint or CMD is not executable |
| 127 | Command not found | Entrypoint binary doesn't exist in the image |
| 137 | Killed (SIGKILL) | Out of memory (OOMKilled) or `docker kill` |
| 139 | Segmentation fault | Application memory corruption |
| 143 | Terminated (SIGTERM) | Graceful shutdown or timeout |

To see the exit code of an exited container:
```bash
docker inspect <container_id> --format='{{.State.ExitCode}}'
```

---

## Wrong or Missing Entrypoint / CMD

**Symptom:** Exit code 126 or 127. Logs say "executable file not found" or "permission denied".

**Diagnosis:**
```bash
# Inspect the image's default entrypoint and command
docker inspect <image_name> --format='{{.Config.Entrypoint}} {{.Config.Cmd}}'

# Check if the binary exists inside the image
docker run --entrypoint /bin/sh <image_name> -c "which myapp && ls -la /usr/local/bin/myapp"
```

**Fix:**
- Ensure the entrypoint binary is installed in the Dockerfile.
- Check that the file has execute permissions: `chmod +x /path/to/entrypoint`.
- Verify the path in CMD/ENTRYPOINT matches the actual binary path in the image.

---

## Container Starts and Immediately Exits

**Symptom:** Container shows "Exited (0)" or "Exited (1)" seconds after starting.

**Cause:** The main process inside the container completed or crashed. Docker containers run as long as their main process (PID 1) is alive.

**Common mistakes:**
1. Running a background daemon that detaches (e.g., `nginx &` starts nginx in background, then the shell script exits).
2. App fails due to a missing environment variable or config file.
3. Database dependency not yet ready (race condition on startup).

**Fix:**
```bash
# Keep the container alive for debugging
docker run -it <image_name> /bin/bash

# Check environment variables
docker run --env-file .env <image_name>

# Add a startup health check with retry logic
docker run -e DB_HOST=db <image_name>
```

For databases: use a wait script or Docker health checks:
```dockerfile
HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
  CMD pg_isready -U postgres || exit 1
```

---

## Out of Memory (OOMKilled) — Exit Code 137

**Symptom:** Exit code 137, container logs cut off abruptly, kernel logs show "Out of memory: Kill process".

**Diagnosis:**
```bash
docker inspect <container_id> | grep -A5 OOMKilled
# "OOMKilled": true means memory limit was hit
```

**Fix:**
- Increase the memory limit: `docker run -m 512m <image_name>`
- Profile memory usage: `docker stats <container_name>` (live memory/CPU)
- Fix memory leak in the application.

---

## Docker Networking Issues

### Port Not Reachable

**Symptom:** `curl localhost:8080` fails even though the container is running.

**Check:**
```bash
docker ps                          # is the port mapped? (0.0.0.0:8080->8080/tcp)
docker port <container_name>       # list all port mappings
netstat -tlnp | grep 8080         # is the host port in use by something else?
```

**Fix:**
- Ensure you used `-p host_port:container_port` when running: `docker run -p 8080:80 nginx`
- The app inside the container must listen on `0.0.0.0`, not `127.0.0.1`.
- If using Docker Compose, confirm the `ports:` key is set (not just `expose:`).

### Container Can't Reach Another Container

```bash
# List networks
docker network ls

# Inspect a network
docker network inspect bridge

# Two containers communicate by service name in a user-defined network
docker network create mynet
docker run --network mynet --name db postgres
docker run --network mynet --name app myapp  # app can reach db at hostname "db"
```

DNS resolution between containers only works on user-defined networks, not the default bridge network.

---

## Volume Mount Issues

**Symptom:** App can't find files, or writes aren't persisting.

**Diagnosis:**
```bash
docker inspect <container_id> --format='{{json .Mounts}}' | python3 -m json.tool
```

**Common mistakes:**
- Mounting a host directory that doesn't exist (Docker creates it as root-owned).
- Bind mount path is wrong (relative paths work differently per OS).
- File permissions: container runs as non-root user but mounted files are owned by root.

**Fix:**
```bash
# Correct bind mount syntax
docker run -v /absolute/host/path:/container/path <image>

# Fix permissions for non-root containers
docker run -v /data:/data -u $(id -u):$(id -g) <image>
```

---

## Image Pull Failures

```bash
docker pull myregistry.example.com/myimage:tag
# "unauthorized: authentication required"
```

**Fix:**
```bash
# Login to the registry
docker login myregistry.example.com

# For ECR (AWS)
aws ecr get-login-password --region us-east-1 | docker login --username AWS \
  --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com
```

---

## Useful Debugging Commands

```bash
# Full container details
docker inspect <container_name>

# Enter a running container
docker exec -it <container_name> /bin/bash

# Enter a stopped container (run a new one from the same image)
docker run -it --entrypoint /bin/bash <image_name>

# Check resource usage live
docker stats

# See recent events (start, stop, kill, OOM)
docker events --since 1h

# Check image layers for large layers
docker history <image_name>
```
