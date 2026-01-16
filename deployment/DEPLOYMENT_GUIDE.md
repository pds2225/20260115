# ☁️ 클라우드 배포 가이드

## 📑 목차

- [배포 옵션 비교](#배포-옵션-비교)
- [AWS 배포](#aws-배포)
- [GCP 배포](#gcp-배포)
- [Azure 배포](#azure-배포)
- [배포 전 체크리스트](#배포-전-체크리스트)
- [비용 예측](#비용-예측)
- [트러블슈팅](#트러블슈팅)

---

## 배포 옵션 비교

| 항목 | AWS ECS | GCP Cloud Run | Azure Container Apps |
|------|---------|---------------|---------------------|
| **관리 편의성** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **비용** | 중간 | 낮음 (pay-per-use) | 중간 |
| **확장성** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Cold Start** | 없음 | 있음 | 있음 |
| **최소 인스턴스** | 필요 | 0 가능 | 0 가능 |
| **네트워킹** | VPC 필수 | Serverless VPC | VNET 지원 |

### 권장 사용 사례

- **AWS ECS**: 엔터프라이즈급, 복잡한 네트워킹, 기존 AWS 인프라
- **GCP Cloud Run**: 스타트업, 빠른 배포, 비용 최적화 우선
- **Azure Container Apps**: 하이브리드 클라우드, Microsoft 생태계

---

## AWS 배포

### 사전 요구사항

```bash
# AWS CLI 설치
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# 인증 설정
aws configure
# AWS Access Key ID: YOUR_KEY
# AWS Secret Access Key: YOUR_SECRET
# Default region name: ap-northeast-2
# Default output format: json
```

### 방법 1: 스크립트로 배포 (빠름)

```bash
cd deployment/aws

# 환경 변수 설정
export AWS_REGION=ap-northeast-2

# 배포 실행
chmod +x deploy-aws.sh
./deploy-aws.sh production
```

### 방법 2: CloudFormation으로 배포 (권장)

```bash
# 스택 생성
aws cloudformation create-stack \
  --stack-name hs-code-production \
  --template-body file://cloudformation-template.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=production \
    ParameterKey=DesiredCount,ParameterValue=2 \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-northeast-2

# 진행 상황 확인
aws cloudformation describe-stacks \
  --stack-name hs-code-production \
  --region ap-northeast-2

# 스택 완료 대기
aws cloudformation wait stack-create-complete \
  --stack-name hs-code-production \
  --region ap-northeast-2

# 출력 확인
aws cloudformation describe-stacks \
  --stack-name hs-code-production \
  --query 'Stacks[0].Outputs' \
  --region ap-northeast-2
```

### AWS 주요 설정

#### ECS Task Definition

```json
{
  "family": "hs-code-task",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [
    {
      "name": "hs-code-api",
      "image": "YOUR_ECR_URI:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "ENVIRONMENT", "value": "production"},
        {"name": "REDIS_HOST", "value": "redis.prod.local"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/hs-code",
          "awslogs-region": "ap-northeast-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### Auto Scaling 설정

```bash
# Target Tracking Policy
aws application-autoscaling put-scaling-policy \
  --policy-name hs-code-cpu-scaling \
  --service-namespace ecs \
  --resource-id service/hs-code-cluster/hs-code-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleInCooldown": 60,
    "ScaleOutCooldown": 60
  }'
```

---

## GCP 배포

### 사전 요구사항

```bash
# gcloud CLI 설치
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# 초기화
gcloud init

# 프로젝트 설정
gcloud config set project YOUR_PROJECT_ID
```

### 방법 1: 스크립트로 배포

```bash
cd deployment/gcp

# 환경 변수 설정
export GCP_PROJECT_ID=your-project-id
export GCP_REGION=asia-northeast3

# 배포 실행
chmod +x deploy-gcp.sh
./deploy-gcp.sh production
```

### 방법 2: Terraform으로 배포 (권장)

```bash
cd deployment/gcp

# Terraform 초기화
terraform init

# 계획 확인
terraform plan \
  -var="project_id=your-project-id" \
  -var="region=asia-northeast3" \
  -var="environment=production"

# 배포
terraform apply \
  -var="project_id=your-project-id" \
  -var="region=asia-northeast3" \
  -var="environment=production"

# 출력 확인
terraform output cloud_run_url
```

### GCP 주요 설정

#### Cloud Run YAML

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hs-code-api
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "1"
        autoscaling.knative.dev/maxScale: "10"
        run.googleapis.com/vpc-access-connector: projects/PROJECT/locations/REGION/connectors/CONNECTOR
    spec:
      serviceAccountName: hs-code-sa@PROJECT.iam.gserviceaccount.com
      containers:
      - image: gcr.io/PROJECT/hs-code-analyzer:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: production
        - name: REDIS_HOST
          value: 10.0.0.3
        resources:
          limits:
            cpu: "2"
            memory: 2Gi
```

#### Cloud Build (CI/CD)

```yaml
# cloudbuild.yaml
steps:
  # Build
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/hs-code-analyzer:$COMMIT_SHA', '.']

  # Push
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/hs-code-analyzer:$COMMIT_SHA']

  # Deploy
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'hs-code-api'
      - '--image'
      - 'gcr.io/$PROJECT_ID/hs-code-analyzer:$COMMIT_SHA'
      - '--region'
      - 'asia-northeast3'
      - '--platform'
      - 'managed'

images:
  - 'gcr.io/$PROJECT_ID/hs-code-analyzer:$COMMIT_SHA'
```

---

## Azure 배포

### 사전 요구사항

```bash
# Azure CLI 설치
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# 로그인
az login

# 구독 설정
az account set --subscription YOUR_SUBSCRIPTION_ID
```

### 배포 실행

```bash
cd deployment/azure

# 환경 변수 설정
export AZURE_LOCATION=koreacentral

# 배포 실행
chmod +x deploy-azure.sh
./deploy-azure.sh production
```

### Azure 주요 설정

#### Container App Configuration

```json
{
  "properties": {
    "configuration": {
      "ingress": {
        "external": true,
        "targetPort": 8000,
        "transport": "auto"
      },
      "registries": [
        {
          "server": "hscodeacr.azurecr.io",
          "username": "hscodeacr",
          "passwordSecretRef": "registry-password"
        }
      ]
    },
    "template": {
      "containers": [
        {
          "image": "hscodeacr.azurecr.io/hs-code-analyzer:latest",
          "name": "hs-code-api",
          "resources": {
            "cpu": 1.0,
            "memory": "2Gi"
          },
          "env": [
            {"name": "ENVIRONMENT", "value": "production"},
            {"name": "REDIS_HOST", "secretRef": "redis-host"}
          ]
        }
      ],
      "scale": {
        "minReplicas": 1,
        "maxReplicas": 10,
        "rules": [
          {
            "name": "http-rule",
            "http": {
              "metadata": {
                "concurrentRequests": "50"
              }
            }
          }
        ]
      }
    }
  }
}
```

---

## 배포 전 체크리스트

### 1. 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# 필수 환경 변수 설정
vim .env
```

**필수 항목:**
- ✅ `SECRET_KEY` - 보안 키 생성
- ✅ `REDIS_HOST` - Redis 호스트
- ✅ `DATABASE_URL` - 데이터베이스 URL (옵션)
- ✅ `ALLOWED_ORIGINS` - CORS 설정

### 2. 보안 설정

```bash
# 강력한 비밀번호 생성
openssl rand -base64 32

# SSH 키 생성 (필요시)
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
```

### 3. 도메인 및 SSL

```bash
# Let's Encrypt SSL 인증서
certbot certonly --standalone -d api.yourdomain.com

# 또는 AWS Certificate Manager / GCP Managed Certificates 사용
```

### 4. 모니터링 설정

- [ ] CloudWatch (AWS) / Cloud Monitoring (GCP) / Application Insights (Azure) 활성화
- [ ] 알림 채널 설정 (이메일, Slack, PagerDuty)
- [ ] 로그 집계 설정

### 5. 백업 전략

- [ ] Redis 데이터 백업 (RDB/AOF)
- [ ] 데이터베이스 자동 백업
- [ ] 설정 파일 버전 관리

---

## 비용 예측

### AWS (월간)

| 서비스 | 사양 | 예상 비용 |
|--------|------|-----------|
| ECS Fargate | 2 tasks, 0.5 vCPU, 1GB | $30 |
| ALB | Standard | $20 |
| ElastiCache Redis | cache.t3.micro | $15 |
| CloudWatch Logs | 5GB | $5 |
| **총계** | | **$70** |

### GCP (월간)

| 서비스 | 사양 | 예상 비용 |
|--------|------|-----------|
| Cloud Run | 1M requests, 1 vCPU, 2GB | $15 |
| Memorystore Redis | 1GB Basic | $25 |
| Cloud Logging | 5GB | $2 |
| **총계** | | **$42** |

### Azure (월간)

| 서비스 | 사양 | 예상 비용 |
|--------|------|-----------|
| App Service | B1 Linux | $13 |
| Redis Cache | Basic C0 | $17 |
| Application Insights | 1GB | $2 |
| **총계** | | **$32** |

> 💡 **팁**: 개발 환경은 야간/주말 자동 중지로 비용 50% 절감 가능

---

## 트러블슈팅

### 1. 컨테이너가 시작되지 않음

```bash
# AWS
aws ecs describe-tasks --cluster CLUSTER --tasks TASK_ID

# GCP
gcloud logging read "resource.type=cloud_run_revision" --limit 50

# Azure
az webapp log tail --name APP_NAME --resource-group RG
```

**일반적인 원인:**
- 포트 설정 오류 (8000번 확인)
- 환경 변수 누락
- 메모리 부족
- 헬스체크 실패

### 2. Redis 연결 실패

```bash
# 네트워크 확인
telnet REDIS_HOST 6379

# Redis 상태 확인
redis-cli -h REDIS_HOST ping
```

**해결 방법:**
- VPC/VNET 피어링 확인
- 보안 그룹/방화벽 규칙 확인
- Redis 비밀번호 확인

### 3. 높은 지연 시간

**원인 분석:**
```bash
# AWS X-Ray / GCP Cloud Trace / Azure Application Insights 사용

# 수동 테스트
time curl https://your-api.com/predict -X POST -d '{"hs_code": "33"}'
```

**최적화:**
- Redis 캐시 적중률 확인
- 리전 변경 (가까운 리전)
- Auto Scaling 설정 조정

### 4. 예산 초과

```bash
# AWS
aws ce get-cost-forecast

# GCP
gcloud billing budgets list

# Azure
az consumption budget list
```

**비용 절감 방법:**
- Reserved Instances (AWS) / Committed Use Discounts (GCP)
- Auto Scaling 최소 인스턴스 감소
- 로그 보존 기간 단축
- 개발 환경 자동 중지

---

## CI/CD 파이프라인

### GitHub Actions 예제

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  deploy-aws:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-northeast-2

      - name: Deploy
        run: |
          cd deployment/aws
          ./deploy-aws.sh production

  deploy-gcp:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup gcloud
        uses: google-github-actions/setup-gcloud@v0
        with:
          project_id: ${{ secrets.GCP_PROJECT_ID }}
          service_account_key: ${{ secrets.GCP_SA_KEY }}

      - name: Deploy
        run: |
          cd deployment/gcp
          ./deploy-gcp.sh production
```

---

## 보안 Best Practices

### 1. Secrets 관리

```bash
# AWS Secrets Manager
aws secretsmanager create-secret \
  --name hs-code/prod/api-key \
  --secret-string "YOUR_SECRET"

# GCP Secret Manager
echo -n "YOUR_SECRET" | gcloud secrets create api-key --data-file=-

# Azure Key Vault
az keyvault secret set \
  --vault-name hs-code-vault \
  --name api-key \
  --value "YOUR_SECRET"
```

### 2. 네트워크 보안

- ✅ VPC/VNET 프라이빗 서브넷 사용
- ✅ 보안 그룹/NSG 최소 권한 원칙
- ✅ WAF (Web Application Firewall) 설정
- ✅ DDoS 방어 활성화

### 3. 컨테이너 보안

```bash
# 이미지 스캔
docker scan your-image:tag

# Snyk 사용
snyk test --docker your-image:tag
```

---

## 성능 모니터링

### 주요 지표

| 지표 | 목표 | 알림 임계값 |
|------|------|-----------|
| 응답 시간 | < 500ms | > 1s |
| 에러율 | < 1% | > 5% |
| CPU 사용률 | < 70% | > 85% |
| 메모리 사용률 | < 80% | > 90% |
| 캐시 적중률 | > 80% | < 60% |

---

## 더 알아보기

- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
- [GCP Best Practices](https://cloud.google.com/architecture/framework)
- [Azure Architecture Center](https://docs.microsoft.com/azure/architecture/)
- [12-Factor App](https://12factor.net/)
- [Container Best Practices](https://cloud.google.com/architecture/best-practices-for-building-containers)
