pipeline {
    agent any
    
    triggers {
        // GitHub Webhook 수신 시 자동 트리거 설정
        GenericTrigger(
            genericVariables: [
                [key: 'ref', value: '$.ref']
            ],
            causeString: 'Triggered by Git Webhook',
            regexpFilterText: '$ref',
            regexpFilterExpression: 'refs/heads/main'
        )
    }

    stages {
        stage('Checkout') {
            steps {
                echo '📦 Checking out latest code from Git repository...'
                checkout scm
            }
        }
        
        stage('Docker Build & Deploy to Local Host') {
            steps {
                echo '🚀 Building images and deploying containers to local host Docker (DooD)...'
                sh 'cp /var/jenkins_home/.env_host .env || touch .env'
                sh 'docker compose build'
                sh 'docker compose up -d --no-deps backend frontend'
                sh 'docker image prune -f'
            }
        }
    }
    
    post {
        success {
            echo '✅ [SUCCESS] AI Council successfully built and deployed to local Docker host via Jenkins!'
        }
        failure {
            echo '❌ [FAILURE] Deployment failed. Please inspect Jenkins console output.'
        }
    }
}
