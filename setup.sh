#!/bin/bash
# setup.sh - Full stack setup script

set -e

echo "🚀 Setting up Elasticsearch AI Assistant"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Create environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your API keys before starting"
fi

# Build and start services
echo "🏗️  Building and starting services..."
docker-compose -f docker-compose.yml up --build -d

echo "⏳ Waiting for services to be ready..."
sleep 30

# Check service health
echo "🏥 Checking service health..."
docker-compose -f docker-compose.yml ps

# Show access URLs
echo ""
echo "✅ Setup complete!"
echo "🌐 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "🔍 Elasticsearch: http://localhost:9200"
echo "📊 OTEL Collector metrics: http://localhost:8889"
echo ""
echo "📖 Check the logs with: docker-compose logs -f"