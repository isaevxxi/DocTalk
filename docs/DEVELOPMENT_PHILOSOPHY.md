# Development Philosophy

## Why We Start Minimal

### The Problem with "Kitchen Sink" Development Environments

Many projects start with **everything enabled from day one**:
- 11+ containers running
- Gigabytes of Docker images downloaded
- Services you won't use for months
- Slow startup times
- High memory/CPU usage
- Confusion about what's actually needed

### Our Approach: Progressive Enhancement

**Start with the bare minimum, add complexity as needed.**

## Development Stages

### Stage 1: Core Development (Current)
**What you need:**
- PostgreSQL (database)
- Redis (cache/sessions)
- MinIO (file storage)

**What you DON'T need yet:**
- Vault (no secrets to manage yet)
- Jaeger/Prometheus/Loki (no performance issues to debug)
- Jitsi/coturn (WebRTC features not implemented)

**Command:** `make up` (3 containers, ~50MB download)

### Stage 2: Feature Development
**Add as needed:**
- WebRTC services when implementing video calls
- Vault when managing per-tenant encryption keys
- Full observability stack when debugging performance

**Command:** `make up-full` (11 containers, ~500MB download)

### Stage 3: Production-Like Testing
**Before deployment:**
- Full stack with all services
- Load testing with k6
- Security scanning
- Performance profiling

## Benefits

1. **Faster onboarding** - New developers can start coding in minutes, not hours
2. **Lower resource usage** - Your laptop stays responsive
3. **Clearer dependencies** - You learn what each service does as you add it
4. **Reduced cognitive load** - Focus on code, not infrastructure
5. **Cheaper CI/CD** - Minimal containers = faster pipeline runs

## When to Use Full Stack

- Testing integrations (e.g., audit logging to Loki)
- Performance benchmarking
- Before creating a PR for production-critical features
- Debugging distributed tracing issues
- Load testing

## Configuration Files

- `docker-compose.dev.yml` - Minimal setup (default)
- `docker-compose.yml` - Full production-like stack
- `.env` - Shared configuration

## Adding New Services

When you need a new service:

1. Add it to `docker-compose.dev.yml` if it's **essential**
2. Add it to `docker-compose.yml` if it's **optional/monitoring**
3. Document in SETUP.md when developers should enable it
4. Update Makefile with any new commands

## Example Workflow

```bash
# Day 1: Start coding
make up                    # PostgreSQL, Redis, MinIO
make dev-backend           # Start API
make dev-frontend          # Start UI

# Week 2: Need WebRTC
make down
make up-full              # Now includes Jitsi/coturn

# Month 2: Performance issues
# Already have full observability stack running
# Check Grafana dashboards at localhost:3001
```

## Comparison

| Aspect | Minimal (`make up`) | Full (`make up-full`) |
|--------|---------------------|----------------------|
| Containers | 3 | 11 |
| Download size | ~50MB | ~500MB |
| Startup time | ~10s | ~2min |
| Memory usage | ~500MB | ~2GB |
| When to use | Daily development | Integration testing |

## Philosophy

> "Premature optimization is the root of all evil" - Donald Knuth

This applies to **infrastructure** too. Don't pay the cost of services you're not using yet.

## Questions?

**Q: But won't I need Vault eventually?**
A: Yes! But not on day 1. Add it when you implement per-tenant encryption.

**Q: What about observability?**
A: FastAPI has built-in logging. Add Prometheus/Grafana when you have something to monitor.

**Q: Isn't this more complex (two docker-compose files)?**
A: No - the Makefile abstracts it. Most developers will just run `make up` and never think about it.

**Q: What if I want to develop a feature that needs service X?**
A: Add it to your local `docker-compose.override.yml` or run `make up-full` temporarily.

---

**TL;DR:** Start minimal, scale up as needed, keep development fast.
