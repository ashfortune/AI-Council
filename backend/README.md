# LLM Project Framework (FastAPI)

대표님, 이 프로젝트는 FastAPI를 기반으로 구축된 LLM 서비스 백엔드 프레임워크입니다.

## 🚀 시작하기

### 1. 환경 변수 설정
`.env` 파일을 열어 `GOOGLE_API_KEY`를 설정해 주세요.

### 2. 가상환경 구축 및 패키지 설치
```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Mac/Linux

# 필수 패키지 설치
pip install -r requirements.txt
```

### 3. 서버 실행
```bash
python app/main.py
```

## 🛠 주요 기능
- **FastAPI Core**: 비동기 처리를 지원하는 고성능 API 서버
- **LLM Service**: Gemini 1.5 Pro/Flash 통합 지원
- **Structured IO**: Pydantic v2를 이용한 엄격한 데이터 검증
- **Swagger UI**: `/docs` 경로에서 API 자동 문서화 제공

## 📂 폴더 구조
- `app/api`: 엔드포인트 정의
- `app/core`: 프로젝트 설정 및 유틸리티
- `app/services`: LLM 연동 로직
- `app/schemas`: 데이터 입출력 모델
