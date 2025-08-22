# Docker Buildx Bake Integration

This project now supports Docker Buildx Bake for improved build performance, better caching, and parallel builds.

## Quick Start

### 1. Setup Docker Buildx Bake

```bash
# Enable bake integration
export COMPOSE_BAKE=true

# Setup buildx builder (one-time setup)
make bake-setup
# or
./bake.sh setup
```

### 2. Build with Bake (Faster!)

```bash
# Build all services with bake (parallel, cached)
make bake-build
# or
./bake.sh build

# Build only specific services
make bake-build-backend
make bake-build-frontend
make bake-build-gateway
```

### 3. Run with Docker Compose

```bash
# Start services (using pre-built bake images)
export COMPOSE_BAKE=true
docker compose up -d
```

## Benefits of Docker Bake

✅ **Parallel Builds**: All services build simultaneously instead of sequentially  
✅ **Better Caching**: Advanced caching strategies reduce rebuild times  
✅ **Multi-Platform**: Support for ARM64 and AMD64 in production builds  
✅ **Advanced Features**: BuildKit features like mount caches, secrets, etc.  
✅ **CI/CD Ready**: Better suited for automated build pipelines  

## Build Targets

### Development Builds
- **Target**: `dev`
- **Features**: Fast builds, local caching
- **Usage**: `make bake-build-dev` or `./bake.sh dev`

### Production Builds  
- **Target**: `prod`
- **Features**: Multi-platform, registry caching, optimized
- **Usage**: `make bake-build-prod` or `./bake.sh prod`

### Individual Services
- **Backend**: `make bake-build-backend` or `./bake.sh build backend`
- **Frontend**: `make bake-build-frontend` or `./bake.sh build frontend`
- **Gateway**: `make bake-build-gateway` or `./bake.sh build gateway`

## Configuration

### Environment Variables

Create `.env.bake` (copy from `.env.bake.example`):

```bash
# Registry for multi-platform builds
REGISTRY=your-registry.com/

# Image tag
TAG=latest

# Cache configuration
CACHE_FROM=type=local,src=/tmp/.buildx-cache
CACHE_TO=type=local,dest=/tmp/.buildx-cache-new,mode=max

# Build arguments
PYTHON_VERSION=3.11
NODE_VERSION=20
```

### Cache Strategies

#### Local Cache (Development)
```bash
CACHE_FROM=type=local,src=/tmp/.buildx-cache
CACHE_TO=type=local,dest=/tmp/.buildx-cache-new,mode=max
```

#### Registry Cache (CI/CD)
```bash
CACHE_FROM=type=registry,ref=your-registry.com/cache:buildcache
CACHE_TO=type=registry,ref=your-registry.com/cache:buildcache,mode=max
```

## Performance Comparison

### Traditional Docker Compose Build
```bash
time docker compose build
# Typical result: ~3-5 minutes (sequential builds)
```

### Docker Bake Build
```bash
time make bake-build
# Typical result: ~1-2 minutes (parallel builds + caching)
```

## Integration with Existing Workflow

### Replace Your Current Build Commands

❌ **Old way:**
```bash
docker compose build
docker compose up -d
```

✅ **New way with Bake:**
```bash
export COMPOSE_BAKE=true
make bake-build
docker compose up -d
```

### Makefile Integration

The project includes updated Makefile targets:

```bash
make bake-setup       # One-time buildx setup
make bake-build       # Build all services with bake
make bake-build-dev   # Build development images
make bake-build-prod  # Build production images
make bake-clean-cache # Clean build cache
```

## Troubleshooting

### BuildKit Not Available
```bash
# Enable buildkit in Docker daemon
echo '{"features":{"buildkit":true}}' > ~/.docker/daemon.json
sudo systemctl restart docker
```

### Builder Creation Fails
```bash
# Remove and recreate builder
docker buildx rm elasticsearch-builder
make bake-setup
```

### Cache Issues
```bash
# Clean all caches
make bake-clean-cache
docker buildx prune -a
```

## CI/CD Integration

For automated builds in CI/CD:

```yaml
# GitHub Actions example
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v2

- name: Build with Bake
  run: |
    export COMPOSE_BAKE=true
    docker buildx bake prod
```

## Migration Guide

1. **Install/Enable Docker Buildx** (included in Docker Desktop 19.03+)
2. **Run setup**: `make bake-setup`  
3. **Test build**: `make bake-build`
4. **Update CI/CD** to use bake commands
5. **Set environment**: `export COMPOSE_BAKE=true` in your shell profile

## Files Added

- `docker-bake.hcl` - Main bake configuration
- `docker-compose.bake.yml` - Compose overrides for bake
- `bake.sh` - Helper script for bake operations
- `.env.bake.example` - Environment variable template
