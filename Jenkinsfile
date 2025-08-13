pipeline {
    agent any

    environment {
        // Set environment variables for testing
        ELASTICSEARCH_URL = 'http://localhost:9200'
        ELASTICSEARCH_VERIFY_CERTS = 'false'
        LOG_LEVEL = 'INFO'
    }

    stages {
        stage('Prepare Environment') {
            steps {
                echo '🔧 Preparing environment...'
                sh 'docker --version'
                sh 'docker compose --version'
            }
        }

        stage('Build Application') {
            steps {
                echo '🏗️ Building application containers...'
                sh 'make build'
            }
        }

        stage('Setup External Elasticsearch') {
            steps {
                echo '🔍 Setting up external Elasticsearch...'
                sh 'make setup-external'
            }
        }

        stage('Start Services') {
            steps {
                echo '🚀 Starting application services...'
                sh 'make up-external'
                
                echo '⏳ Waiting for services to be ready...'
                sh '''
                    echo "Waiting for backend to start..."
                    for i in {1..30}; do
                        if curl -s http://localhost:8000/api/health > /dev/null; then
                            echo "Backend is ready"
                            break
                        fi
                        echo "Attempt $i/30: Backend not ready yet, waiting..."
                        sleep 2
                    done
                    
                    echo "Waiting for frontend to start..."
                    for i in {1..30}; do
                        if curl -s http://localhost:3000 > /dev/null; then
                            echo "Frontend is ready"
                            break
                        fi
                        echo "Attempt $i/30: Frontend not ready yet, waiting..."
                        sleep 2
                    done
                '''
            }
        }

        stage('Run Health Checks') {
            steps {
                echo '🏥 Performing health checks...'
                sh '''
                    echo "Backend health check:"
                    curl -s http://localhost:8000/api/health | jq '.' || echo "Backend health check failed"
                    
                    echo "Frontend health check:"
                    curl -s http://localhost:3000 > /dev/null && echo "Frontend: OK" || echo "Frontend: Not responding"
                '''
            }
        }

        stage('Run Tests') {
            steps {
                echo '🧪 Running application tests...'
                sh '''
                    # Install test dependencies in backend container
                    docker compose exec -T backend pip install pytest pytest-asyncio pytest-html
                    
                    # Run the tests and capture output
                    docker compose exec -T backend python -m pytest test/ \
                        --junitxml=test_results.xml \
                        --html=test_report.html \
                        --self-contained-html \
                        -v \
                        --tb=short || true
                    
                    # Copy test results from container to host
                    docker compose cp backend:/app/test_results.xml ./test_results.xml || echo "Could not copy test_results.xml"
                    docker compose cp backend:/app/test_report.html ./test_report.html || echo "Could not copy test_report.html"
                    
                    echo "Test results captured"
                '''
            }
        }

        stage('Generate Test Report') {
            steps {
                echo '📊 Generating test report...'
                sh '''
                    # Create a simple test summary
                    echo "=== TEST EXECUTION SUMMARY ===" > test_summary.txt
                    echo "Date: $(date)" >> test_summary.txt
                    echo "Build: ${BUILD_NUMBER}" >> test_summary.txt
                    echo "" >> test_summary.txt
                    
                    if [ -f test_results.xml ]; then
                        echo "JUnit XML test results found" >> test_summary.txt
                        # Extract test summary from XML if available
                        grep -o 'tests="[^"]*"' test_results.xml | head -1 >> test_summary.txt || echo "Could not parse test count" >> test_summary.txt
                        grep -o 'failures="[^"]*"' test_results.xml | head -1 >> test_summary.txt || echo "No failures found" >> test_summary.txt
                        grep -o 'errors="[^"]*"' test_results.xml | head -1 >> test_summary.txt || echo "No errors found" >> test_summary.txt
                    else
                        echo "No JUnit XML results found" >> test_summary.txt
                    fi
                    
                    echo "" >> test_summary.txt
                    echo "=== DOCKER LOGS ===" >> test_summary.txt
                    docker compose logs --tail=50 backend >> test_summary.txt 2>&1 || echo "Could not capture backend logs" >> test_summary.txt
                    
                    cat test_summary.txt
                '''
            }
        }
    }

    post {
        always {
            echo '🧹 Cleaning up and archiving artifacts...'
            
            // Archive test results
            script {
                if (fileExists('test_results.xml')) {
                    archiveArtifacts artifacts: 'test_results.xml', fingerprint: true
                    publishTestResults testResultsPattern: 'test_results.xml'
                }
                if (fileExists('test_report.html')) {
                    archiveArtifacts artifacts: 'test_report.html', fingerprint: true
                }
                if (fileExists('test_summary.txt')) {
                    archiveArtifacts artifacts: 'test_summary.txt', fingerprint: true
                }
            }
            
            // Clean up
            sh '''
                echo "Stopping services..."
                make down || true
                echo "Cleanup completed"
            '''
        }
        success {
            echo '✅ Pipeline completed successfully!'
        }
        failure {
            echo '❌ Pipeline failed!'
        }
    }
}
