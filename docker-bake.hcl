# Docker Buildx Bake configuration for Elasticsearch Data Assistant
# This enables parallel builds, better caching, and improved performance

variable "REGISTRY" {
  default = ""
}

variable "TAG" {
  default = "latest"
}

variable "CACHE_FROM" {
  default = "type=local,src=/tmp/.buildx-cache"
}

variable "CACHE_TO" {
  default = "type=local,dest=/tmp/.buildx-cache-new,mode=max"
}

# Define the group for all services
group "default" {
  targets = ["backend", "gateway", "frontend"]
}

# Backend service
target "backend" {
  context = "./backend"
  dockerfile = "Dockerfile"
  tags = [
    "${REGISTRY}elasticsearch-data-assistant-backend:${TAG}",
    "${REGISTRY}elasticsearch-data-assistant-backend:latest"
  ]
  cache-from = ["${CACHE_FROM}"]
  cache-to = ["${CACHE_TO}"]
  platforms = ["linux/amd64"]
  
  # Build arguments that can be overridden
  args = {
    PYTHON_VERSION = "3.11"
  }
}

# Gateway service
target "gateway" {
  context = "./gateway"
  dockerfile = "Dockerfile"
  tags = [
    "${REGISTRY}elasticsearch-data-assistant-gateway:${TAG}",
    "${REGISTRY}elasticsearch-data-assistant-gateway:latest"
  ]
  cache-from = ["${CACHE_FROM}"]
  cache-to = ["${CACHE_TO}"]
  platforms = ["linux/amd64"]
  
  # Build arguments that can be overridden
  args = {
    NODE_VERSION = "20"
  }
}

# Frontend service
target "frontend" {
  context = "./frontend"
  dockerfile = "Dockerfile"
  tags = [
    "${REGISTRY}elasticsearch-data-assistant-frontend:${TAG}",
    "${REGISTRY}elasticsearch-data-assistant-frontend:latest"
  ]
  cache-from = ["${CACHE_FROM}"]
  cache-to = ["${CACHE_TO}"]
  platforms = ["linux/amd64"]
  
  # Build arguments that can be overridden
  args = {
    NODE_VERSION = "20"
  }
}

# Development group for faster iteration
group "dev" {
  targets = ["backend-dev", "gateway-dev", "frontend-dev"]
}

# Development variants with different cache strategies
target "backend-dev" {
  inherits = ["backend"]
  tags = ["elasticsearch-data-assistant-backend:dev"]
  cache-from = ["type=local,src=/tmp/.buildx-cache-backend"]
  cache-to = ["type=local,dest=/tmp/.buildx-cache-backend,mode=max"]
}

target "gateway-dev" {
  inherits = ["gateway"]
  tags = ["elasticsearch-data-assistant-gateway:dev"]
  cache-from = ["type=local,src=/tmp/.buildx-cache-gateway"]
  cache-to = ["type=local,dest=/tmp/.buildx-cache-gateway,mode=max"]
}

target "frontend-dev" {
  inherits = ["frontend"]
  tags = ["elasticsearch-data-assistant-frontend:dev"]
  cache-from = ["type=local,src=/tmp/.buildx-cache-frontend"]
  cache-to = ["type=local,dest=/tmp/.buildx-cache-frontend,mode=max"]
}

# Production group with optimizations
group "prod" {
  targets = ["backend-prod", "gateway-prod", "frontend-prod"]
}

target "backend-prod" {
  inherits = ["backend"]
  tags = ["elasticsearch-data-assistant-backend:prod"]
  cache-from = [
    "type=local,src=/tmp/.buildx-cache-backend",
    "type=registry,ref=${REGISTRY}elasticsearch-data-assistant-backend:buildcache"
  ]
  cache-to = [
    "type=local,dest=/tmp/.buildx-cache-backend,mode=max",
    "type=registry,ref=${REGISTRY}elasticsearch-data-assistant-backend:buildcache,mode=max"
  ]
  platforms = ["linux/amd64", "linux/arm64"]
}

target "gateway-prod" {
  inherits = ["gateway"]
  tags = ["elasticsearch-data-assistant-gateway:prod"]
  cache-from = [
    "type=local,src=/tmp/.buildx-cache-gateway",
    "type=registry,ref=${REGISTRY}elasticsearch-data-assistant-gateway:buildcache"
  ]
  cache-to = [
    "type=local,dest=/tmp/.buildx-cache-gateway,mode=max",
    "type=registry,ref=${REGISTRY}elasticsearch-data-assistant-gateway:buildcache,mode=max"
  ]
  platforms = ["linux/amd64", "linux/arm64"]
}

target "frontend-prod" {
  inherits = ["frontend"]
  tags = ["elasticsearch-data-assistant-frontend:prod"]
  cache-from = [
    "type=local,src=/tmp/.buildx-cache-frontend",
    "type=registry,ref=${REGISTRY}elasticsearch-data-assistant-frontend:buildcache"
  ]
  cache-to = [
    "type=local,dest=/tmp/.buildx-cache-frontend,mode=max",
    "type=registry,ref=${REGISTRY}elasticsearch-data-assistant-frontend:buildcache,mode=max"
  ]
  platforms = ["linux/amd64", "linux/arm64"]
}
