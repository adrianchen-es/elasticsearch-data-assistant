#!/bin/bash

# Docker Bake setup and usage script for Elasticsearch Data Assistant
# This script helps you use Docker Buildx Bake for faster, parallel builds

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if Docker Buildx is available
check_buildx() {
    if ! docker buildx version >/dev/null 2>&1; then
        print_error "Docker Buildx is not available. Please install Docker Desktop or enable buildx."
        exit 1
    fi
    print_status "Docker Buildx is available"
}

# Setup buildx builder
setup_builder() {
    print_step "Setting up Docker Buildx builder..."
    
    # Create or use existing builder
    BUILDER_NAME="elasticsearch-builder"
    
    if docker buildx inspect "$BUILDER_NAME" >/dev/null 2>&1; then
        print_status "Builder '$BUILDER_NAME' already exists"
        docker buildx use "$BUILDER_NAME"
    else
        print_step "Creating new builder '$BUILDER_NAME'..."
        docker buildx create --name "$BUILDER_NAME" --use --bootstrap
    fi
    
    print_status "Builder setup complete"
}

# Build using bake
build_with_bake() {
    local target=${1:-"default"}
    
    print_step "Building with Docker Bake (target: $target)..."
    print_status "This enables parallel builds and better caching for improved performance"
    
    # Set environment variable for compose integration
    export COMPOSE_BAKE=true
    
    # Build with bake
    docker buildx bake "$target"
    
    print_status "Build completed successfully!"
}

# Show usage
usage() {
    cat << EOF
Docker Bake Setup Script for Elasticsearch Data Assistant

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    setup           Setup Docker Buildx builder
    build [target]  Build images using bake (default: all services)
    dev             Build development images
    prod            Build production images
    clean           Clean build cache
    help            Show this help

Build Targets:
    default         Build all services (backend, gateway, frontend)
    dev             Build development versions
    prod            Build production versions with multi-platform support
    backend         Build only backend service
    gateway         Build only gateway service  
    frontend        Build only frontend service

Examples:
    $0 setup                    # Setup buildx builder
    $0 build                    # Build all services
    $0 build backend            # Build only backend
    $0 dev                      # Build development images
    $0 prod                     # Build production images

Benefits of Docker Bake:
    • Parallel builds for faster performance
    • Better caching strategies
    • Multi-platform support
    • Advanced build features
    • Integration with docker-compose

EOF
}

# Main script logic
main() {
    case "${1:-help}" in
        "setup")
            check_buildx
            setup_builder
            ;;
        "build")
            check_buildx
            build_with_bake "${2:-default}"
            ;;
        "dev")
            check_buildx
            build_with_bake "dev"
            ;;
        "prod")
            check_buildx
            build_with_bake "prod"
            ;;
        "clean")
            print_step "Cleaning Docker Buildx cache..."
            docker buildx prune -f
            print_status "Cache cleaned"
            ;;
        "help"|*)
            usage
            ;;
    esac
}

# Run main function
main "$@"
