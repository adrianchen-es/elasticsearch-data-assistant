pipeline {
    agent any

    stages {
        stage('Build & Execute') {
            steps {
                echo 'Building the application...'
                sh 'make setup-external' // Assuming a Makefile exists with a build target
            }
        }

        stage('Run Tests') {
            steps {
                echo 'Running tests...'
                sh 'pytest --junitxml=test_results.xml test/'
            }
        }
    }

    post {
        always {
            echo 'Archiving test results...'
            archiveArtifacts artifacts: 'test_results.xml', fingerprint: true
        }
    }
}
