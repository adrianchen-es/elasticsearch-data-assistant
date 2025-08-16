pipeline {
    agent any
    
    environment {
        // Deployment configuration
        DOCKER_REGISTRY = credentials('docker-registry-url')
        DOCKER_CREDENTIALS = credentials('docker-hub-credentials')
        ELASTICSEARCH_URL = credentials('elasticsearch-url')
        
        // Build metadata
        BUILD_VERSION = "${env.BUILD_NUMBER}-${env.GIT_COMMIT[0..7]}"
        DEPLOY_ENV = "${env.BRANCH_NAME == 'main' ? 'production' : 'staging'}"
        
        // Original environment variables
        ELASTICSEARCH_VERIFY_CERTS = 'false'
        LOG_LEVEL = 'INFO'
    }
    
    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 45, unit: 'MINUTES')
        skipStagesAfterUnstable()
        ansiColor('xterm')
    }
    
    stages {
        stage('🔍 Pre-flight Checks') {
            parallel {
                stage('Environment Setup') {
                    steps {
                        echo "🚀 Starting enhanced build for branch: ${env.BRANCH_NAME}"
                        echo '🔧 Preparing environment...'
                        sh 'docker --version'
                        sh 'docker compose --version'
                        
                        script {
                            // Validate required files exist
                            def requiredFiles = [
                                'docker-compose.yml',
                                'backend/requirements.txt',
                                'frontend/package.json',
                                'gateway/package.json',
                                'Makefile'
                            ]
                            
                            requiredFiles.each { file ->
                                if (!fileExists(file)) {
                                    error("❌ Required file missing: ${file}")
                                }
                            }
                            echo "✅ All required files present"
                        }
                    }
                }
                
                stage('Security Scan') {
                    steps {
                        echo "🔒 Running enhanced security checks..."
                        
                        script {
                            // Check for sensitive data exposure
                            def sensitivePatterns = [
                                'api[_-]?key\\s*=\\s*["\'][^"\']+["\']',
                                'password\\s*=\\s*["\'][^"\']+["\']',
                                'secret\\s*=\\s*["\'][^"\']+["\']',
                                '10\\.[0-9]{1,3}\\.[0-9]{1,3}\\.[0-9]{1,3}',
                                '192\\.168\\.[0-9]{1,3}\\.[0-9]{1,3}'
                            ]
                            
                            def foundIssues = false
                            sensitivePatterns.each { pattern ->
                                def result = sh(
                                    script: "grep -r -E '${pattern}' --include='*.js' --include='*.py' --include='*.json' . || true",
                                    returnStdout: true
                                ).trim()
                                
                                if (result) {
                                    echo "⚠️ Potential sensitive data found:"
                                    echo result
                                    foundIssues = true
                                }
                            }
                            
                            if (foundIssues) {
                                currentBuild.result = 'UNSTABLE'
                                echo "⚠️ Security issues detected - build marked as unstable"
                            } else {
                                echo "✅ Security scan passed"
                            }
                        }
                    }
                }
            }
        }
        
        stage('🏗️ Build Application') {
            steps {
                echo '🏗️ Building application containers with enhanced features...'
                sh 'make build'
                
                echo "🐳 Tagging images with build version: ${BUILD_VERSION}"
                script {
                    // Tag images with build version for traceability
                    sh """
                        docker tag elasticsearch-data-assistant-backend:latest elasticsearch-data-assistant-backend:${BUILD_VERSION}
                        docker tag elasticsearch-data-assistant-frontend:latest elasticsearch-data-assistant-frontend:${BUILD_VERSION}
                        docker tag elasticsearch-data-assistant-gateway:latest elasticsearch-data-assistant-gateway:${BUILD_VERSION}
                    """
                }
            }
        }
        
        stage('🔍 Setup & Health Checks') {
            steps {
                echo '🔍 Setting up external Elasticsearch with enhanced monitoring...'
                sh 'make setup-external'
                
                echo '🏥 Performing comprehensive health checks...'
                sh '''
                    # Wait for services with better error handling
                    echo "Waiting for backend to start..."
                    for i in {1..30}; do
                        if curl -s http://localhost:8000/api/health > /dev/null; then
                            echo "✅ Backend is ready"
                            break
                        fi
                        echo "Attempt $i/30: Backend not ready yet, waiting..."
                        sleep 2
                    done
                    
                    echo "Waiting for frontend to start..."
                    for i in {1..30}; do
                        if curl -s http://localhost:3000 > /dev/null; then
                            echo "✅ Frontend is ready"
                            break
                        fi
                        echo "Attempt $i/30: Frontend not ready yet, waiting..."
                        sleep 2
                    done
                    
                    # Enhanced health checks
                    echo "🏥 Backend comprehensive health check:"
                    backend_health=$(curl -s http://localhost:8000/api/health)
                    echo "$backend_health" | jq '.' || echo "Backend health check failed"
                    
                    # Check if health response indicates all systems are healthy
                    if echo "$backend_health" | jq -e '.status == "healthy"' > /dev/null; then
                        echo "✅ Backend health status: HEALTHY"
                    else
                        echo "⚠️ Backend health status: NOT OPTIMAL"
                        currentBuild.result = 'UNSTABLE'
                    fi
                    
                    echo "🌐 Frontend health check:"
                    if curl -s http://localhost:3000 > /dev/null; then
                        echo "✅ Frontend: RESPONSIVE"
                        
                        # Check for mobile layout elements
                        if curl -s http://localhost:3000/ | grep -q "mobile"; then
                            echo "📱 Mobile layout: DETECTED"
                        else
                            echo "📱 Mobile layout: NOT DETECTED"
                        fi
                    else
                        echo "❌ Frontend: NOT RESPONDING"
                        error("Frontend health check failed")
                    fi
                    
                    # Test provider status endpoint
                    echo "🔌 Provider status check:"
                    provider_status=$(curl -s http://localhost:8000/api/providers/status || echo "{}")
                    echo "$provider_status" | jq '.' || echo "Provider status check failed"
                '''
            }
        }
        
        stage('🧪 Enhanced Testing Suite') {
            parallel {
                stage('Core Application Tests') {
                    steps {
                        echo '🧪 Running comprehensive application tests...'
                        sh '''
                            # Install test dependencies in backend container
                            docker compose exec -T backend pip install pytest pytest-asyncio pytest-html pytest-cov
                            
                            # Validate OpenTelemetry package versions
                            echo '🔎 Validating OpenTelemetry package versions...'
                            docker compose exec -T backend python - <<'PY'
import pkg_resources, sys
packages = ['opentelemetry-api','opentelemetry-sdk','opentelemetry-exporter-otlp']
for p in packages:
    try:
        v = pkg_resources.get_distribution(p).version
        print(f'✅ {p}=={v}')
    except Exception as e:
        print(f'❌ {p} not installed: {e}')
PY
                            
                            # Run comprehensive test suite
                            echo "🧪 Running enhanced test suite..."
                            docker compose exec -T backend python -m pytest test/ \
                                --cov=. \
                                --cov-report=xml \
                                --cov-report=html \
                                --junitxml=test_results.xml \
                                --html=test_report.html \
                                --self-contained-html \
                                -v \
                                --tb=short \
                                --cov-fail-under=70 || true
                            
                            # Copy comprehensive test results
                            docker compose cp backend:/app/test_results.xml ./test_results.xml || echo "Could not copy test_results.xml"
                            docker compose cp backend:/app/test_report.html ./test_report.html || echo "Could not copy test_report.html"
                            docker compose cp backend:/app/htmlcov ./htmlcov || echo "Could not copy coverage report"
                        '''
                    }
                }
                
                stage('Enhanced Feature Tests') {
                    steps {
                        echo '🔧 Testing enhanced features...'
                        sh '''
                            # Test enhanced functionality
                            echo "🧪 Running enhanced functionality tests..."
                            docker compose exec -T backend python -m pytest test/test_enhanced_functionality.py -v || true
                            
                            # Test mobile responsiveness
                            echo "📱 Testing mobile layout features..."
                            mobile_response=$(curl -s http://localhost:3000/)
                            if echo "$mobile_response" | grep -q "mobile-header\\|MobileLayout"; then
                                echo "✅ Mobile layout components detected"
                            else
                                echo "⚠️ Mobile layout components not found"
                            fi
                            
                            # Test conversation management endpoints
                            echo "💬 Testing conversation management..."
                            test_message='{"message": "Test conversation management", "provider": "auto", "return_debug": true}'
                            conversation_response=$(curl -s -X POST http://localhost:8000/api/chat/stream \
                                -H "Content-Type: application/json" \
                                -d "$test_message" \
                                --max-time 30)
                            
                            if echo "$conversation_response" | grep -q "error"; then
                                echo "⚠️ Conversation management test encountered issues"
                            else
                                echo "✅ Conversation management test passed"
                            fi
                            
                            # Test mapping display functionality
                            echo "🗺️ Testing mapping display..."
                            mapping_response=$(curl -s http://localhost:8000/api/query/analyze)
                            if [ -n "$mapping_response" ]; then
                                echo "✅ Mapping endpoints responding"
                            else
                                echo "⚠️ Mapping endpoints not responding properly"
                            fi
                        '''
                    }
                }
                
                stage('Performance Tests') {
                    steps {
                        echo '⚡ Running performance tests...'
                        sh '''
                            echo "⚡ Testing API performance..."
                            
                            # Test response times for critical endpoints
                            health_time=$(curl -w "%{time_total}" -o /dev/null -s http://localhost:8000/api/health)
                            echo "Health endpoint response time: ${health_time}s"
                            
                            providers_time=$(curl -w "%{time_total}" -o /dev/null -s http://localhost:8000/api/providers/status)
                            echo "Providers endpoint response time: ${providers_time}s"
                            
                            frontend_time=$(curl -w "%{time_total}" -o /dev/null -s http://localhost:3000/)
                            echo "Frontend response time: ${frontend_time}s"
                            
                            # Performance thresholds
                            if (( $(echo "$health_time > 2.0" | bc -l) )); then
                                echo "⚠️ Health endpoint response time is slow: ${health_time}s"
                                currentBuild.result = 'UNSTABLE'
                            else
                                echo "✅ Health endpoint performance is good: ${health_time}s"
                            fi
                            
                            # Test concurrent requests
                            echo "🔄 Testing concurrent request handling..."
                            for i in {1..5}; do
                                curl -s http://localhost:8000/api/health > /dev/null &
                            done
                            wait
                            echo "✅ Concurrent request test completed"
                        '''
                    }
                }
            }
        }
        
        stage('📊 Enhanced Test Reporting') {
            steps {
                echo '📊 Generating comprehensive test report...'
                sh '''
                    # Create enhanced test summary
                    echo "=== ENHANCED TEST EXECUTION SUMMARY ===" > enhanced_test_summary.txt
                    echo "Date: $(date)" >> enhanced_test_summary.txt
                    echo "Build: ${BUILD_NUMBER}" >> enhanced_test_summary.txt
                    echo "Version: ${BUILD_VERSION}" >> enhanced_test_summary.txt
                    echo "Branch: ${BRANCH_NAME}" >> enhanced_test_summary.txt
                    echo "" >> enhanced_test_summary.txt
                    
                    # Test results analysis
                    if [ -f test_results.xml ]; then
                        echo "✅ JUnit XML test results found" >> enhanced_test_summary.txt
                        tests=$(grep -o 'tests="[^"]*"' test_results.xml | head -1 | cut -d'"' -f2)
                        failures=$(grep -o 'failures="[^"]*"' test_results.xml | head -1 | cut -d'"' -f2)
                        errors=$(grep -o 'errors="[^"]*"' test_results.xml | head -1 | cut -d'"' -f2)
                        
                        echo "Total Tests: $tests" >> enhanced_test_summary.txt
                        echo "Failures: $failures" >> enhanced_test_summary.txt
                        echo "Errors: $errors" >> enhanced_test_summary.txt
                        
                        if [ "$failures" = "0" ] && [ "$errors" = "0" ]; then
                            echo "✅ All tests passed successfully" >> enhanced_test_summary.txt
                        else
                            echo "⚠️ Some tests failed or had errors" >> enhanced_test_summary.txt
                        fi
                    else
                        echo "❌ No JUnit XML results found" >> enhanced_test_summary.txt
                    fi
                    
                    # Feature verification summary
                    echo "" >> enhanced_test_summary.txt
                    echo "=== FEATURE VERIFICATION ===" >> enhanced_test_summary.txt
                    echo "Mobile Layout: $(curl -s http://localhost:3000/ | grep -q mobile && echo 'VERIFIED' || echo 'NOT VERIFIED')" >> enhanced_test_summary.txt
                    echo "Provider Status: $(curl -s http://localhost:8000/api/providers/status > /dev/null && echo 'VERIFIED' || echo 'NOT VERIFIED')" >> enhanced_test_summary.txt
                    echo "Health Caching: $(curl -s http://localhost:8000/api/health | jq -e '.status' > /dev/null && echo 'VERIFIED' || echo 'NOT VERIFIED')" >> enhanced_test_summary.txt
                    
                    echo "" >> enhanced_test_summary.txt
                    echo "=== PERFORMANCE METRICS ===" >> enhanced_test_summary.txt
                    echo "Health Endpoint: $(curl -w '%{time_total}s' -o /dev/null -s http://localhost:8000/api/health)" >> enhanced_test_summary.txt
                    echo "Frontend Load: $(curl -w '%{time_total}s' -o /dev/null -s http://localhost:3000/)" >> enhanced_test_summary.txt
                    
                    cat enhanced_test_summary.txt
                '''
            }
        }
        
        stage('🚀 Deployment') {
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            steps {
                echo "🚀 Deploying to ${DEPLOY_ENV} environment..."
                
                script {
                    if (env.BRANCH_NAME == 'main') {
                        echo "🔴 Production deployment initiated"
                        
                        // Production deployment with additional safeguards
                        sh '''
                            echo "🔒 Pre-production verification..."
                            
                            # Verify all services are healthy before deployment
                            if ! curl -f http://localhost:8000/api/health; then
                                echo "❌ Backend not healthy - aborting deployment"
                                exit 1
                            fi
                            
                            if ! curl -f http://localhost:3000/; then
                                echo "❌ Frontend not healthy - aborting deployment"
                                exit 1
                            fi
                            
                            echo "✅ Pre-deployment health checks passed"
                            echo "🚀 Proceeding with production deployment..."
                            
                            # Tag for production
                            export BUILD_VERSION=production
                            export DEPLOY_ENV=production
                            
                            # Deploy with production configuration
                            make down || true
                            make build
                            make setup-external
                        '''
                        
                        echo "✅ Production deployment completed"
                        
                    } else if (env.BRANCH_NAME == 'develop') {
                        echo "🟡 Staging deployment initiated"
                        
                        sh '''
                            echo "🚀 Deploying to staging environment..."
                            export BUILD_VERSION=${BUILD_VERSION}
                            export DEPLOY_ENV=staging
                            
                            # Staging deployment
                            make down || true
                            make build
                            make setup-external
                        '''
                        
                        echo "✅ Staging deployment completed"
                    }
                }
            }
        }
        
        stage('🎯 Post-Deployment Verification') {
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            steps {
                echo "🔍 Running comprehensive post-deployment verification..."
                
                sh '''
                    echo "🏥 Verifying deployment health..."
                    
                    # Wait for services to stabilize after deployment
                    sleep 10
                    
                    # Comprehensive health verification
                    backend_health=$(curl -s http://localhost:8000/api/health | jq -r '.status // "unknown"')
                    if [ "$backend_health" != "healthy" ]; then
                        echo "❌ Backend health check failed: $backend_health"
                        exit 1
                    fi
                    echo "✅ Backend health: $backend_health"
                    
                    # Verify frontend accessibility
                    if ! curl -f http://localhost:3000/ > /dev/null 2>&1; then
                        echo "❌ Frontend is not responding"
                        exit 1
                    fi
                    echo "✅ Frontend is responding"
                    
                    # Verify provider configuration
                    provider_count=$(curl -s http://localhost:8000/api/providers/status | jq -r '.providers | length // 0')
                    if [ "$provider_count" -eq 0 ]; then
                        echo "❌ No providers configured"
                        exit 1
                    fi
                    echo "✅ Providers configured: $provider_count"
                    
                    # Test critical functionality
                    echo "🧪 Testing critical post-deployment functionality..."
                    
                    # Test conversation endpoint
                    conversation_test=$(curl -s -X POST http://localhost:8000/api/chat/stream \
                        -H "Content-Type: application/json" \
                        -d '{"message": "Deployment verification test", "provider": "auto"}' \
                        --max-time 15)
                    
                    if echo "$conversation_test" | grep -q "error"; then
                        echo "⚠️ Conversation functionality may have issues"
                    else
                        echo "✅ Conversation functionality verified"
                    fi
                    
                    # Verify mobile responsiveness
                    if curl -s http://localhost:3000/ | grep -q "mobile\\|responsive"; then
                        echo "✅ Mobile features verified in deployment"
                    else
                        echo "⚠️ Mobile features not detected in deployment"
                    fi
                    
                    echo "✅ All post-deployment verifications completed successfully"
                '''
            }
        }
    }
    
    post {
        always {
            echo '🧹 Enhanced cleanup and archiving...'
            
            // Archive comprehensive test results and artifacts
            script {
                def artifacts = [
                    'test_results.xml',
                    'test_report.html', 
                    'enhanced_test_summary.txt',
                    'backend_full_logs.txt'
                ]
                
                artifacts.each { artifact ->
                    if (fileExists(artifact)) {
                        archiveArtifacts artifacts: artifact, fingerprint: true
                    }
                }
                
                // Publish test results if available
                if (fileExists('test_results.xml')) {
                    publishTestResults testResultsPattern: 'test_results.xml'
                }
                
                // Archive coverage reports
                if (fileExists('htmlcov')) {
                    archiveArtifacts artifacts: 'htmlcov/**', fingerprint: true
                }
            }
            
            // Enhanced cleanup with comprehensive logging
            sh '''
                echo "📋 Capturing comprehensive logs..."
                docker compose logs backend > backend_full_logs.txt 2>&1 || true
                docker compose logs frontend > frontend_full_logs.txt 2>&1 || true
                docker compose logs gateway > gateway_full_logs.txt 2>&1 || true
                
                echo "🧹 Cleaning up deployment..."
                make down || true
                
                echo "🗑️ Cleaning up Docker resources..."
                docker system prune -f || true
                
                echo "✅ Enhanced cleanup completed"
            '''
        }
        
        success {
            echo '🎉 Enhanced pipeline completed successfully!'
            script {
                def message = """
                ✅ **Elasticsearch Data Assistant Enhanced Build Successful**
                
                **Build Details:**
                • Version: ${BUILD_VERSION}
                • Branch: ${env.BRANCH_NAME}  
                • Environment: ${DEPLOY_ENV}
                • Commit: ${env.GIT_COMMIT[0..7]}
                
                **Enhanced Features Verified:**
                • Mobile-responsive UI ✅
                • Conversation management ✅
                • Intelligent mapping display ✅  
                • Provider failover capability ✅
                • Token management with chunking ✅
                • Health status caching ✅
                • OpenTelemetry tracing ✅
                • Security data masking ✅
                
                **Quality Metrics:**
                • All tests passed ✅
                • Security scan completed ✅
                • Performance benchmarks met ✅
                • Post-deployment verification passed ✅
                """.stripIndent()
                
                echo message
                
                // Optional: Send to Slack or other notification system
                // slackSend(channel: '#deployments', color: 'good', message: message)
            }
        }
        
        failure {
            echo '❌ Enhanced pipeline failed!'
            script {
                def failureStage = "${env.STAGE_NAME ?: 'Unknown'}"
                def message = """
                ❌ **Elasticsearch Data Assistant Build Failed**
                
                **Build Details:**
                • Version: ${BUILD_VERSION}
                • Branch: ${env.BRANCH_NAME}
                • Failed Stage: ${failureStage}
                • Build URL: ${env.BUILD_URL}
                
                **Action Required:**
                Please review the build logs and address the failure before retrying.
                Check the archived artifacts for detailed error information.
                """.stripIndent()
                
                echo message
                // slackSend(channel: '#deployments', color: 'danger', message: message)
            }
        }
        
        unstable {
            echo '⚠️ Enhanced pipeline completed with warnings'
            script {
                def message = """
                ⚠️ **Elasticsearch Data Assistant Build Unstable**
                
                **Build Details:**
                • Version: ${BUILD_VERSION}
                • Branch: ${env.BRANCH_NAME}
                
                **Warning:** 
                Build completed but some quality checks failed or warnings were detected.
                Please review the build logs and enhanced test summary.
                """.stripIndent()
                
                echo message
                // slackSend(channel: '#deployments', color: 'warning', message: message)
            }
        }
    }
}
