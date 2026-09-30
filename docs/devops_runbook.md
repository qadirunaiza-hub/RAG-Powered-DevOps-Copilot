# DevOps Operations Runbook

## High CPU Usage Investigation

When a server or pod shows unexpectedly high CPU usage, follow this structured approach.

### Step 1: Identify the Top CPU Consumers

```bash
# Interactive real-time view (press 'P' to sort by CPU)
top
htop

# One-shot snapshot sorted by CPU
ps aux --sort=-%cpu | head -20

# Single process CPU over time
pidstat -u 1 5   # sample every 1 second, 5 times
```

**Reading `top` output:**
- `%us` — user-space CPU (application code)
- `%sy` — kernel/system CPU (syscalls, I/O)
- `%wa` — CPU time spent waiting for I/O (high = disk bottleneck)
- `load average: 1.5, 2.0, 1.8` — 1min, 5min, 15min averages; values > number of cores indicate CPU saturation

### Step 2: Inspect the Specific Process

```bash
# Get the PID from top/htop, then:
# See all threads of a process
top -H -p <PID>

# Trace system calls (what is the process actually doing?)
strace -p <PID> -e trace=all -T    # -T shows time per syscall

# Flame graph (requires Linux perf)
perf top -p <PID>
```

### Step 3: Common Causes and Fixes

| Cause | Symptom | Fix |
|-------|---------|-----|
| Infinite loop | One process at 100% CPU | Debug the application code |
| Too many threads | Many processes at high CPU | Tune thread pool size |
| GC pressure (JVM/Python) | Periodic CPU spikes | Increase heap, reduce object creation |
| Runaway cron job | CPU spikes at regular intervals | `crontab -l`, check `/var/log/cron` |
| Log file flooding | `python` or `java` process with high CPU and I/O | Reduce log verbosity |

---

## High Memory Usage Investigation

```bash
# Overall memory summary
free -h
# "available" column is what's actually usable (includes reclaimable cache)

# Detailed breakdown
cat /proc/meminfo | grep -E "MemTotal|MemFree|MemAvailable|Cached|Buffers|SwapUsed"

# Top memory consumers
ps aux --sort=-%mem | head -20

# Memory map of a specific process
pmap -x <PID> | sort -k3 -n | tail -20
```

### Swap Usage

High swap usage causes severe performance degradation.
```bash
swapon --show           # see swap devices
vmstat 1 5              # si/so columns = swap in/swap out per second; >0 = swapping
```

**Fix:** Add swap, reduce application memory usage, or add more RAM. If a container: increase memory limit or optimize the application.

---

## Disk Space Investigation

```bash
# Overall disk usage per filesystem
df -h

# Find what's using space in a directory
du -sh /var/* | sort -h | tail -20
du -sh /home/* | sort -h

# Find the largest files on the system
find / -type f -size +500M 2>/dev/null | xargs ls -lh | sort -k5 -h

# Docker-specific: see how much space Docker is using
docker system df
docker system prune -f    # remove stopped containers, dangling images, unused networks
```

### Common Disk Hogs

- **Log files:** Check `/var/log/`, application log directories. Implement log rotation with `logrotate`.
- **Docker images:** `docker images | sort -k7 -h`. Remove unused images: `docker image prune -a`.
- **Core dumps:** `find / -name "core.*" -size +100M`
- **Temporary files:** `/tmp`, `/var/tmp`

---

## Disk I/O Investigation

```bash
# Real-time I/O per device
iostat -x 1 5
# %util near 100% = disk is saturated

# Which processes are doing I/O?
iotop                    # interactive (requires root)
iotop -ao                # accumulated I/O, non-interactive

# I/O wait on processes
ps aux | awk '{print $8, $11}' | grep "^D"   # D = uninterruptible sleep (I/O wait)
```

---

## Network Troubleshooting

### Connectivity Issues

```bash
# Basic connectivity
ping <host>
traceroute <host>

# Is a service listening on a port?
ss -tlnp | grep 8080
netstat -tlnp | grep 8080

# Can we reach a remote port?
curl -v http://<host>:<port>/health
telnet <host> <port>

# DNS resolution
nslookup <hostname>
dig <hostname>
```

### Bandwidth and Connections

```bash
# Active TCP connections
ss -s           # summary
ss -tn          # all TCP connections

# Real-time network bandwidth per interface
iftop           # interactive
nethogs         # per-process bandwidth

# Capture packets for deep inspection
tcpdump -i eth0 -n host <target_ip> and port 8080 -w capture.pcap
```

### Common Network Issues

| Issue | Command to Diagnose | Fix |
|-------|-------------------|-----|
| DNS not resolving | `dig`, `nslookup` | Check `/etc/resolv.conf`, DNS server |
| Port blocked | `curl`, `telnet` | Check firewall: `iptables -L`, `ufw status` |
| High latency | `ping`, `traceroute` | Network congestion, wrong route |
| Connection reset | `tcpdump` | Application crash, firewall drop rule |

---

## Log Analysis

```bash
# Follow logs in real-time
tail -f /var/log/syslog
journalctl -f -u nginx    # systemd service logs

# Search for errors in the last hour
journalctl --since "1 hour ago" | grep -i error

# Count error frequency
grep "ERROR" /var/log/app.log | awk '{print $1, $2}' | sort | uniq -c | sort -rn

# Extract slow queries (example: >1000ms)
grep "duration: [0-9]\{4,\}" /var/log/postgresql/postgresql.log
```

---

## Process Management

```bash
# Send signals to processes
kill -SIGTERM <PID>     # graceful shutdown (app should handle this)
kill -SIGKILL <PID>     # force kill (can't be ignored)
kill -SIGHUP <PID>      # reload config (many daemons support this)

# Manage systemd services
systemctl status nginx
systemctl restart nginx
systemctl enable nginx    # auto-start on boot

# Change process priority
nice -n 10 <command>           # start with lower priority
renice -n 10 -p <PID>         # change priority of running process
```

---

## Quick Health Checks — One-Liner Runbook

```bash
# System summary
uptime && free -h && df -h && ss -s

# All failed systemd services
systemctl --failed

# Recent kernel errors
dmesg --level=err,crit,alert,emerg | tail -20

# Who is logged in and what are they running
who && w

# Last 10 reboots
last reboot | head -10
```
