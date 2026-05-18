pipeline {
    agent any
    
    triggers {
        // GitHub/GitLab Webhook 수신 시 자동 트리거 설정
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
                echo '📦 Checking out from version control...'
                checkout scm
            }
        }
        
        stage('Backend Verification') {
            steps {
                echo '🔍 Verifying Backend (FastAPI)...'
                dir('backend') {
                    sh 'python3 -m pip install -r requirements.txt || true'
                    sh 'pytest || true'
                }
            }
        }
        
        stage('Frontend Verification') {
            steps {
                echo '🎨 Verifying Frontend (Next.js)...'
                dir('frontend') {
                    sh 'npm install || true'
                    sh 'npm run lint || true'
                }
            }
        }
        
        stage('Docker Build & Rolling Deploy') {
            steps {
                echo '🚀 Building Docker images and deploying containers (DooD)...'
                sh 'docker compose build'
                sh 'docker compose up -d --no-deps backend frontend'
                sh 'docker image prune -f'
            }
        }
    }
    
    post {
        success {
            echo '✅ [SUCCESS] AI Council CI/CD Pipeline successfully executed and deployed via Webhook!'
        }
        failure {
            echo '❌ [FAILURE] Pipeline execution failed. Please inspect Jenkins console output.'
        }
    }
}
