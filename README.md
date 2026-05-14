# AI-Council AI Full-Stack Project

대표님, 요청하신 대로 `Source` 디렉토리 내에 백엔드와 프론트엔드가 공존하는 최적화된 구조로 재배치하였습니다.

## 📂 프로젝트 구조
- **`/Source/backend`**: FastAPI 기반 백엔드 (Python 3.10+)
- **`/Source/frontend`**: Next.js 14 기반 프론트엔드 (React, TypeScript)

## 🚀 실행 가이드

### 1. 백엔드 실행 (backend 폴더)
```bash
cd Source/backend
# 가상환경 활성화
source .venv/bin/activate
# 패키지 설치
pip install -r requirements.txt
# 서버 실행
python app/main.py
```
*주의: `Source/.env` 파일에 `GOOGLE_API_KEY`가 설정되어 있어야 합니다. (환경 변수는 Source 루트에서 전역 관리됩니다.)*

### 2. 프론트엔드 실행 (frontend 폴더)
```bash
cd Source/frontend
# 패키지 설치
npm install
# 개발 서버 실행
npm run dev
```
접속 주소: [http://localhost:3000](http://localhost:3000)

## ✨ 아키텍처 특징
- **구조화된 관리**: 백엔드와 프론트엔드를 독립된 모듈로 관리하여 유지보수성을 확보했습니다.
- **프리미엄 디자인**: Glassmorphism 테마의 세련된 UI가 적용되었습니다.
- **확장성**: 향후 데이터베이스 연동 및 새로운 LLM 모델 추가가 용이한 설계입니다.
