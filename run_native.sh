#!/bin/bash

# AI Council Native Run Script (for Mac)

echo "🚀 AI Council 네이티브 환경 실행을 시작합니다..."

# 1. 백엔드 실행 (백그라운드)
echo "📂 백엔드 서버 구동 중..."
cd backend
if [ -d ".venv" ]; then
    source .venv/bin/activate
    pip install -q -r requirements.txt
    uvicorn app.main:app --reload --port 8000 &
    BACKEND_PID=$!
    echo "✅ 백엔드 실행 중... (PID: $BACKEND_PID, Port: 8000)"
else
    echo "❌ .venv 가상환경을 찾을 수 없습니다. backend 디렉토리에서 가상환경을 먼저 생성해 주세요."
    exit 1
fi

# 2. 프론트엔드 실행
echo "📂 프론트엔드 서버 구동 중..."
cd ../frontend
echo "✅ 프론트엔드 실행 준비 완료. 잠시 후 http://localhost:3000 접속이 가능합니다."
npm run dev

# 종료 시 백엔드 프로세스 함께 종료
trap "kill $BACKEND_PID" EXIT
