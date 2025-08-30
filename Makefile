.PHONY: help setup setup-external build up down logs clean health test

help: ## Show this help message
	@echo "Elasticsearch AI Assistant - Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Setup with local Elasticsearch
	@chmod +x setup.sh
	@./setup.sh

setup-external: ## Setup with external Elasticsearch
	@chmod +x setup-external-es.sh
	@./setup-external-es.sh

build: ## Build all services (legacy docker-compose)
	@docker compose build

# Docker Buildx Bake commands for improved performance
bake-setup: ## Setup Docker Buildx for bake
	@echo "Setting up Docker Buildx..."
	@docker buildx create --name elasticsearch-builder --use --bootstrap || true
	@docker buildx inspect --bootstrap

bake-build: ## Build all services using Docker Bake (faster, parallel)
	@echo "Building with Docker Bake for improved performance..."
	@export COMPOSE_BAKE=true && docker buildx bake

bake-build-dev: ## Build development versions using Docker Bake
	@echo "Building development images with Docker Bake..."
	@docker buildx bake dev

bake-build-prod: ## Build production versions using Docker Bake (multi-platform)
	@echo "Building production images with Docker Bake..."
	@docker buildx bake prod

bake-build-backend: ## Build only backend service
	@docker buildx bake backend

bake-build-frontend: ## Build only frontend service
	@docker buildx bake frontend

bake-build-gateway: ## Build only gateway service
	@docker buildx bake gateway

bake-clean-cache: ## Clean buildx cache
	@echo "Cleaning Docker Buildx cache..."
	@docker buildx prune -f

up: ## Start all services
	@docker compose up -d

up-external: ## Start services with external ES
	@docker compose -f docker-compose.external-es.yml up -d

down: ## Stop all services
	@docker compose down
	@docker compose -f docker-compose.external-es.yml down

logs: ## Show logs for all services
	@docker compose logs -f

logs-backend: ## Show backend logs
	@docker compose logs -f backend

logs-frontend: ## Show frontend logs
	@docker compose logs -f frontend

health: ## Check service health
	@echo "Checking service health..."
	@curl -s http://localhost:8000/api/health | jq '.' || echo "Backend not responding"
	@curl -s http://localhost:3000 > /dev/null && echo "Frontend: OK" || echo "Frontend: Not responding"

clean: ## Clean up containers and volumes
	@docker compose down -v
	@docker compose -f docker-compose.external-es.yml down -v
	@docker system prune -f

test-backend: ## Run backend tests
	@cd backend && python -m pytest tests/ -v

dev-backend: ## Run backend in development mode
	@cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Run frontend in development mode
	@cd frontend && npm start