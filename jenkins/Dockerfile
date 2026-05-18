FROM jenkins/jenkins:lts-jdk17
USER root

# 로컬 호스트 도커 데몬 제어(DooD)를 위해 공식 Docker CLI 및 Docker Compose Plugin만 초경량 설치
RUN apt-get update && apt-get install -y curl \
    && curl -fsSL https://get.docker.com | sh \
    && rm -rf /var/lib/apt/lists/*

# 도커 소켓 접근 권한 유지를 위해 root 계정 설정
USER root
