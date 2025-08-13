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

build: ## Build all services
	@docker compose build

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