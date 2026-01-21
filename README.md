# World Bank Data360 API - 데이터 다운로드 및 클리닝 프로젝트

World Bank Data360 API를 활용한 데이터 수집 및 클리닝 자동화 프로젝트입니다.

## 📊 데이터 구조

### World Bank Data360 API 응답 컬럼 (총 23개)

| 컬럼명 | 설명 |
|--------|------|
| `DATABASE_ID` | 데이터베이스 ID (예: WB_WDI) |
| `INDICATOR` | 지표 코드 (예: NY.GDP.MKTP.CD) |
| `REF_AREA` | 국가/지역 코드 (ISO 3자리) |
| `TIME_PERIOD` | 시간 (연도) |
| `OBS_VALUE` | 관측값 (핵심 데이터) |
| `FREQ` | 데이터 빈도 (A=연간) |
| `UNIT_MEASURE` | 측정 단위 (USD, Persons, Percent 등) |
| `UNIT_TYPE` | 단위 타입 |
| `UNIT_MULT` | 단위 배수 (0, 3, 6, 9 등) |
| `TIME_FORMAT` | 시간 형식 |
| `DECIMALS` | 소수점 자릿수 |
| `OBS_STATUS` | 관측 상태 (A=실제값, E=추정값, P=잠정값) |
| `OBS_CONF` | 기밀도 |
| `DATA_SOURCE` | 데이터 출처 |
| `LATEST_DATA` | 최신 데이터 여부 |
| `COMMENT_OBS` | 관측값 주석 |
| `COMMENT_TS` | 시계열 주석 |
| `AGG_METHOD` | 집계 방법 |
| `SEX` | 성별 구분 |
| `AGE` | 연령 구분 |
| `URBANISATION` | 도시화 구분 |
| `COMP_BREAKDOWN_1~3` | 추가 분류 |

## 🚀 사용 방법

### 1. 환경 설정

```bash
# 필요한 패키지 설치
pip install -r requirements.txt
```

### 2. 샘플 데이터 생성 및 클리닝

```bash
python generate_sample_data.py
```

이 스크립트는 다음을 수행합니다:
- World Bank 스타일의 샘플 데이터 생성 (1,000개 레코드)
- 자동 데이터 클리닝
- CSV 및 Excel 파일로 저장

### 3. 실제 API에서 데이터 가져오기 (네트워크 환경에서)

```bash
python fetch_and_clean_data.py
```

## 📁 생성되는 파일

1. **원본 CSV** (`worldbank_raw_*.csv`)
   - 클리닝 전 원본 데이터

2. **클리닝된 CSV** (`worldbank_clean_*.csv`)
   - 클리닝 후 데이터

3. **통합 Excel** (`worldbank_*.xlsx`)
   - **Clean_Data 시트**: 클리닝된 데이터
   - **Raw_Data 시트**: 원본 데이터
   - **Summary 시트**: 데이터 요약 통계
   - **Column_Info 시트**: 컬럼별 상세 정보

## 🧹 데이터 클리닝 프로세스

### 자동으로 수행되는 클리닝 작업:

1. **결측치 처리**
   - OBS_VALUE(핵심 데이터)가 없는 행 제거
   - 모든 값이 NULL인 컬럼 제거
   - 95% 이상 NULL인 컬럼 제거

2. **중복 제거**
   - 완전히 동일한 중복 행 제거

3. **데이터 타입 정규화**
   - TIME_PERIOD → 숫자형
   - OBS_VALUE → 숫자형
   - UNIT_MULT → 숫자형

4. **텍스트 정리**
   - 모든 텍스트 컬럼의 앞뒤 공백 제거

5. **이상치 제거**
   - 음수 OBS_VALUE 제거

6. **정렬 및 인덱스 재설정**
   - TIME_PERIOD, REF_AREA, INDICATOR 기준 정렬

## 📈 샘플 데이터 통계

최근 생성된 샘플 데이터:
- **원본**: 1,050행 × 24컬럼
- **클리닝 후**: 909행 × 18컬럼
- **제거율**: 13.4%
- **시간 범위**: 2015-2023
- **국가 수**: 20개국
- **지표 수**: 5개

### 포함된 지표:
1. `NY.GDP.MKTP.CD` - GDP (현재 미화)
2. `NY.GDP.PCAP.CD` - 1인당 GDP (현재 미화)
3. `SP.POP.TOTL` - 총 인구
4. `SP.URB.TOTL.IN.ZS` - 도시 인구 비율 (%)
5. `SE.PRM.ENRR` - 초등학교 등록률 (%)

## 🔗 API 엔드포인트

### 주요 엔드포인트:

1. **GET /data360/indicators**
   - 데이터셋의 사용 가능한 지표 목록 조회
   - 파라미터: `datasetId`

2. **GET /data360/data**
   - 필터 기반 데이터 조회
   - 필수: `DATABASE_ID`
   - 선택: `INDICATOR`, `REF_AREA`, `TIME_PERIOD`, `timePeriodFrom`, `timePeriodTo` 등

3. **GET /data360/disaggregation**
   - 지표별 분류 항목 조회

4. **POST /data360/metadata**
   - 메타데이터 조회

## 📚 참고 자료

- API 문서: https://data360api.worldbank.org
- OpenAPI 스펙: https://raw.githubusercontent.com/worldbank/open-api-specs/refs/heads/main/Data360%20Open_API.json

## 🛠️ 기술 스택

- Python 3.11+
- pandas - 데이터 처리
- requests - API 호출
- openpyxl - Excel 파일 생성
- numpy - 수치 연산

## 📝 라이선스

이 프로젝트는 World Bank의 공개 데이터를 활용합니다.
