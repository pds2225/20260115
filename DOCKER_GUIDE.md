# 🐳 Docker 실행 가이드

## 빠른 시작

### 1단계: Docker 설치 확인

```bash
docker --version
docker-compose --version
```

### 2단계: 스크립트로 실행 (권장)

```bash
# 전체 스택 시작
./start-docker.sh

# 전체 스택 중지
./stop-docker.sh
```

### 3단계: 접속

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090

---

## 수동 실행

### 전체 스택 시작

```bash
# 빌드 및 시작
docker-compose up -d --build

# 로그 확인
docker-compose logs -f

# 특정 서비스 로그
docker-compose logs -f api
```

### 상태 확인

```bash
# 실행 중인 컨테이너
docker-compose ps

# 리소스 사용량
docker stats
```

### 개별 서비스 재시작

```bash
# API만 재시작
docker-compose restart api

# Redis만 재시작
docker-compose restart redis
```

### 중지 및 정리

```bash
# 컨테이너 중지 (데이터 유지)
docker-compose down

# 컨테이너 + 볼륨 삭제 (완전 정리)
docker-compose down -v

# 이미지까지 삭제
docker-compose down -v --rmi all
```

---

## 서비스 구성

### 1. API (FastAPI)
- **포트**: 8000
- **역할**: 메인 백엔드 API
- **의존성**: Redis
- **헬스체크**: http://localhost:8000/health

### 2. Redis
- **포트**: 6379
- **역할**: 캐시 저장소
- **데이터 지속성**: AOF (Append Only File)
- **볼륨**: redis-data

### 3. Prometheus
- **포트**: 9090
- **역할**: 메트릭 수집
- **설정**: monitoring/prometheus.yml
- **볼륨**: prometheus-data

### 4. Grafana
- **포트**: 3001
- **역할**: 대시보드 시각화
- **로그인**: admin / admin
- **볼륨**: grafana-data

### 5. Alertmanager
- **포트**: 9093
- **역할**: 알림 관리
- **설정**: monitoring/alertmanager.yml
- **볼륨**: alertmanager-data

### 6. Loki
- **포트**: 3100
- **역할**: 로그 수집
- **볼륨**: loki-data

### 7. Promtail
- **역할**: 로그 전송
- **의존성**: Loki

---

## 환경 변수 설정

### .env 파일 생성

```bash
# 템플릿 복사
cp .env.example .env

# 편집
nano .env  # 또는 vi .env
```

### 주요 환경 변수

```env
# API 설정
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=info

# Redis 설정
REDIS_HOST=redis
REDIS_PORT=6379
CACHE_TTL=86400

# Grafana 설정
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin

# 보안
SECRET_KEY=your-secret-key
ALLOWED_ORIGINS=http://localhost:5173
```

---

## 트러블슈팅

### 포트 충돌

```bash
# 포트 사용 확인
sudo lsof -i :8000
sudo lsof -i :6379

# 프로세스 종료
sudo kill -9 <PID>
```

### 볼륨 권한 문제

```bash
# 볼륨 삭제 후 재생성
docker-compose down -v
docker-compose up -d
```

### 메모리 부족

```bash
# 사용하지 않는 이미지/컨테이너 정리
docker system prune -a

# 볼륨 정리
docker volume prune
```

### 로그 확인

```bash
# 전체 로그
docker-compose logs

# 실시간 로그
docker-compose logs -f api

# 마지막 100줄
docker-compose logs --tail=100 api
```

---

## 성능 최적화

### 메모리 제한

`docker-compose.yml`에 추가:

```yaml
services:
  api:
    mem_limit: 1g
    mem_reservation: 512m
```

### CPU 제한

```yaml
services:
  api:
    cpus: '0.5'
```

### 네트워크 최적화

```bash
# Docker 네트워크 확인
docker network inspect 20260115_hs-network

# MTU 설정
docker network create --opt com.docker.network.driver.mtu=1450 custom-network
```

---

## 프로덕션 배포

### Docker Swarm

```bash
# Swarm 초기화
docker swarm init

# 스택 배포
docker stack deploy -c docker-compose.yml hs-code

# 상태 확인
docker stack services hs-code
```

### Kubernetes (Helm)

```bash
# Docker 이미지 빌드 및 푸시
docker build -t your-registry/hs-code-api:latest .
docker push your-registry/hs-code-api:latest

# Helm 차트 배포
helm install hs-code ./k8s/helm-chart
```

---

## 모니터링 대시보드

### Grafana 대시보드 가져오기

1. Grafana 접속: http://localhost:3001
2. 로그인: admin / admin
3. Configuration > Data Sources
4. Prometheus 추가: http://prometheus:9090
5. Dashboards > Import
6. 대시보드 ID 입력:
   - **1860**: Node Exporter Full
   - **3662**: Prometheus 2.0 Overview

### 커스텀 대시보드

```json
{
  "dashboard": {
    "title": "HS Code Analyzer",
    "panels": [
      {
        "title": "API Requests",
        "targets": [
          {
            "expr": "rate(api_requests_total[5m])"
          }
        ]
      }
    ]
  }
}
```

---

## 백업 및 복구

### 데이터 백업

```bash
# Redis 백업
docker exec hs-code-redis redis-cli SAVE
docker cp hs-code-redis:/data/dump.rdb ./backup/

# Grafana 백업
docker cp hs-code-grafana:/var/lib/grafana ./backup/grafana

# Prometheus 백업
docker cp hs-code-prometheus:/prometheus ./backup/prometheus
```

### 데이터 복구

```bash
# Redis 복구
docker cp ./backup/dump.rdb hs-code-redis:/data/
docker-compose restart redis

# Grafana 복구
docker cp ./backup/grafana hs-code-grafana:/var/lib/
docker-compose restart grafana
```

---

## 개발 모드

### 핫 리로드 활성화

`docker-compose.override.yml` 생성:

```yaml
version: '3.8'

services:
  api:
    volumes:
      - ./backend:/app
    command: uvicorn api_v4_production:app --host 0.0.0.0 --port 8000 --reload
```

실행:

```bash
docker-compose up -d
```

---

## 보안 설정

### SSL/TLS 인증서

```bash
# Let's Encrypt 인증서 생성
docker run -it --rm -v ./certs:/etc/letsencrypt certbot/certbot certonly

# docker-compose.yml에 추가
volumes:
  - ./certs:/etc/ssl/certs:ro
```

### 방화벽 설정

```bash
# UFW로 포트 제한
sudo ufw allow 8000/tcp
sudo ufw allow 3001/tcp
sudo ufw enable
```

---

## FAQ

**Q: 컨테이너가 시작되지 않아요**
```bash
# 로그 확인
docker-compose logs api

# 포트 충돌 확인
sudo lsof -i :8000
```

**Q: Redis 연결 오류**
```bash
# Redis 상태 확인
docker-compose exec redis redis-cli PING

# 네트워크 확인
docker network inspect 20260115_hs-network
```

**Q: Grafana에 로그인이 안 돼요**
- 기본 로그인: admin / admin
- 비밀번호 재설정: `docker-compose restart grafana`

---

## 더 알아보기

- [Docker 공식 문서](https://docs.docker.com/)
- [Docker Compose 문서](https://docs.docker.com/compose/)
- [FastAPI Docker 가이드](https://fastapi.tiangolo.com/deployment/docker/)
- [Prometheus 설정](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- [Grafana 대시보드](https://grafana.com/grafana/dashboards/)
