# DS-02 World Bank 데이터 수집·가공 명세 (WSB 기준)

> **문서 버전**: v1.0
> **최종 수정**: 2026-01-28
> **상위 문서**: 구현 계약서 v1 — 6장(데이터 소스 명세), 7장(데이터 품질·전처리 계약)

---

## 0. 문서 목적

본 문서는 DS-02(World Bank Indicators)의 **수집·저장·정규화·점수 산정 규칙**을 구현 수준으로 고정한다.
개발자는 본 문서의 수식·규칙·스키마를 **그대로 구현**하며, 변경 시 CR 절차를 따른다.

---

## 1. DS-02의 역할 정의 (Scope Lock)

| 항목 | 정의 |
|------|------|
| **목적** | 국가 단위 거시 수요·구매력·성장성 보정 |
| **사용 위치** | 후보국 생성 이후 → Score 산정 단계(5.4)에서 **EconomicScore** 계산에만 사용 |
| **사용 단위** | `country-year` (최신 연도 1개만 사용) |
| **사용 금지** | EconomicScore 외 다른 점수 계산에 DS-02 데이터 사용 금지 |

---

## 2. 수집 대상 지표 (WSB 매핑, 7개 고정)

| WSB Field ID | 지표명 | World Bank Indicator Code | 단위 | 용도 |
|--------------|--------|---------------------------|------|------|
| WSB_ECO_01 | GDP (current USD) | `NY.GDP.MKTP.CD` | USD | 로그 스케일 정규화 |
| WSB_ECO_02 | GDP per capita | `NY.GDP.PCAP.CD` | USD | 구매력 지표 (보조) |
| WSB_ECO_03 | GDP growth (annual %) | `NY.GDP.MKTP.KD.ZG` | % | 성장성 가점 |
| WSB_ECO_04 | Import value (goods & services) | `NE.IMP.GNFS.CD` | USD | 수입 수요 규모 |
| WSB_ECO_05 | Import growth (annual %) | `NE.IMP.GNFS.KD.ZG` | % | 수요 증가율 |
| WSB_ECO_06 | Inflation (CPI, %) | `FP.CPI.TOTL.ZG` | % | 리스크 페널티 |
| WSB_ECO_07 | Population | `SP.POP.TOTL` | 명 | 시장 크기 보조지표 |

> **위 7개 지표 외 World Bank 데이터는 v1 범위에서 사용 금지**

### 2.1 명시적 제외 항목 (Out of Scope)

다음 지표는 v1에서 수집·사용하지 않는다:

- 환율 (Exchange Rate)
- 실업률 (Unemployment)
- 제조업 비중 (Manufacturing %)
- FDI (Foreign Direct Investment)
- GNI (Gross National Income)
- PPP 기반 지표
- World Bank Governance Indicators

---

## 3. 데이터 수집 규칙

### 3.1 API 엔드포인트

```
Base URL: https://api.worldbank.org/v2
Format: JSON (format=json)
Per Page: 최대 1000 (per_page=1000)
```

### 3.2 호출 패턴

```
GET /v2/country/{iso2}/indicator/{indicator_code}?date={year_range}&format=json&per_page=1000
```

- `iso2`: ISO 3166-1 alpha-2 국가코드 (ISO3→ISO2 변환 필요)
- `indicator_code`: 2장의 World Bank Indicator Code
- `date`: 연도 범위 (예: `2020:2024`)

### 3.3 수집 대상 국가

- DS-03(CEPII)에 존재하는 모든 ISO3 국가의 ISO2 변환 코드
- ISO3 → ISO2 매핑은 고정 테이블 사용

### 3.4 수집 주기

- **운영**: 스냅샷 기반 (월 1회 또는 수동 트리거)
- **스냅샷 메타**: `/health` 응답의 `data_sources.DS-02.last_snapshot`에 반영

---

## 4. 연도 선택 규칙

### 4.1 최신 유효 연도 선택

```text
target_year = max(year WHERE value IS NOT NULL)
제약: current_year - target_year ≤ 3
```

- 3년 초과 시 → **해당 지표 전체 무효 (결측 처리)**
- 국가별 연도 혼용 허용 (지표 간 연도 동일 조건 없음)

### 4.2 예시

| 국가 | GDP 최신 | Import 최신 | 사용 |
|------|----------|------------|------|
| VNM | 2023 | 2023 | ✅ 둘 다 사용 |
| MMR | 2021 | 2020 | ✅ GDP 사용, Import: 2026-2020=6년 → ❌ 무효 |
| XXX | 2019 | 2019 | ❌ 둘 다 3년 초과 → 후보군 제외 |

---

## 5. 결측값 처리 규칙

### 5.1 필수 지표 결측 → 후보군 제외

| 지표 | 결측 시 처리 |
|------|------------|
| GDP (`WSB_ECO_01`) | 해당 국가 **후보군 제외** (Hard Filter) |
| Import value (`WSB_ECO_04`) | 해당 국가 **후보군 제외** (Hard Filter) |

### 5.2 선택 지표 결측 → 0점 처리

| 지표 | 결측 시 처리 |
|------|------------|
| GDP growth (`WSB_ECO_03`) | 해당 항목 점수 = 0 |
| Import growth (`WSB_ECO_05`) | 해당 항목 점수 = 0 |
| Inflation (`WSB_ECO_06`) | 해당 항목 점수 = 0 (페널티 없음) |
| Population (`WSB_ECO_07`) | 로그 보정에서 제외 |
| GDP per capita (`WSB_ECO_02`) | 보조지표, 점수 미반영 |

### 5.3 금지 사항

- **임의 대체(Imputation) 금지**: 결측값을 평균, 중앙값, 0 등으로 대체하지 않는다
- **0값 → 결측 치환 금지**: 0으로 제공된 값은 결측이 아닌 실제 값으로 간주
- **GDP ≤ 0**: 이상값으로 판정 → 후보군 제외 + 로그 + warning 기록
- **Import value < 0**: 이상값으로 판정 → 후보군 제외 + 로그 + warning 기록

---

## 6. 정규화 규칙 (수식 고정)

### 6.1 로그 스케일 정규화

적용 대상: GDP, Import value, Population

```text
norm(x) = (log(x) - min_log) / (max_log - min_log)
```

- `log` = 자연로그 (`ln`)
- `min_log`, `max_log`: 해당 스냅샷의 전체 후보국 기준 최소/최대
- 결과 범위: 0 ~ 1

### 6.2 퍼센트 지표 클리핑 + 정규화

적용 대상: GDP growth, Import growth, Inflation

**Step 1: 클리핑**

| 지표 | lower | upper |
|------|-------|-------|
| GDP growth (%) | -5 | +10 |
| Import growth (%) | -5 | +15 |
| Inflation (%) | 0 | 15 |

```text
clipped = clip(x, lower, upper)
```

**Step 2: 0-1 정규화**

```text
norm(clipped) = (clipped - lower) / (upper - lower)
```

| 지표 | 정규화 공식 | 결과 범위 |
|------|-----------|----------|
| GDP growth | (clip(x, -5, 10) + 5) / 15 | 0 ~ 1 |
| Import growth | (clip(x, -5, 15) + 5) / 20 | 0 ~ 1 |
| Inflation | clip(x, 0, 15) / 15 | 0 ~ 1 |

---

## 7. EconomicScore 산식 (고정)

### 7.1 수식

```text
EconomicScore =
    0.30 × norm(GDP)
  + 0.25 × norm(ImportValue)
  + 0.20 × norm_clip(GDP_Growth)
  + 0.15 × norm_clip(Import_Growth)
  - 0.10 × norm_clip(Inflation)
```

### 7.2 가중치 표

| 항목 | 가중치 | 방향 | 의미 |
|------|--------|------|------|
| GDP | 0.30 | + | 시장 규모 |
| Import value | 0.25 | + | 수입 수요 |
| GDP growth | 0.20 | + | 성장성 |
| Import growth | 0.15 | + | 수요 증가 |
| Inflation | 0.10 | - | 리스크 감점 |
| **합계** | **1.00** | | |

### 7.3 결과 범위

- 이론적 범위: -0.10 ~ 0.90
- **최소 0 적용**: `max(0, EconomicScore)`
- 최종 범위: **0 ~ 1**

### 7.4 결측 항목 처리

- 결측 항목의 기여분 = 0 (가중치 재분배 없음)
- 예: GDP_growth 결측 → 0.20 × 0 = 0 기여

---

## 8. 저장 스키마 (WSB)

### 8.1 레코드 구조

```json
{
  "country_iso3": "VNM",
  "country_iso2": "VN",
  "year": 2023,
  "snapshot_date": "2026-01-28",
  "indicators": {
    "gdp_usd": 430000000000,
    "gdp_per_capita_usd": 4400,
    "gdp_growth_pct": 5.1,
    "import_value_usd": 345000000000,
    "import_growth_pct": 8.2,
    "inflation_pct": 3.4,
    "population": 100300000
  },
  "normalized": {
    "norm_gdp": 0.72,
    "norm_import_value": 0.68,
    "norm_gdp_growth": 0.67,
    "norm_import_growth": 0.66,
    "norm_inflation": 0.23,
    "norm_population": 0.75
  },
  "economic_score": 0.67,
  "data_quality": {
    "missing_fields": [],
    "stale_fields": [],
    "warnings": []
  }
}
```

### 8.2 필드 정의

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| country_iso3 | string(3) | ✅ | ISO 3166-1 alpha-3 |
| country_iso2 | string(2) | ✅ | ISO 3166-1 alpha-2 |
| year | integer | ✅ | 데이터 기준 연도 (지표별 최신) |
| snapshot_date | string(date) | ✅ | 스냅샷 수집일 |
| indicators.* | number/null | 조건부 | 원본 값 (null = 결측) |
| normalized.* | number/null | 조건부 | 정규화된 값 (0~1) |
| economic_score | number | ✅ | 0 ~ 1 |
| data_quality | object | ✅ | 결측/경고 정보 |

---

## 9. `/predict` 응답 내 DS-02 반영 규격

### 9.1 score_components 내 포함

```json
{
  "score_components": {
    "economic_score": 0.67,
    "trade_potential": 52.0,
    "distance_penalty": -8.4
  }
}
```

### 9.2 explanation 내 DS-02 관련 정보

```json
{
  "explanation": {
    "top_factors": [
      {"factor": "gdp_usd", "direction": "positive", "source": "DS-02"},
      {"factor": "import_value_usd", "direction": "positive", "source": "DS-02"}
    ],
    "data_quality": {
      "missing_fields": [],
      "warnings": [],
      "ds02_year": 2023,
      "ds02_snapshot": "2026-01-28"
    }
  }
}
```

### 9.3 결측 시 warning 예시

```json
{
  "data_quality": {
    "missing_fields": ["gdp_growth_pct", "import_growth_pct"],
    "warnings": [
      "DS-02: GDP growth data unavailable for VNM (year 2023)",
      "DS-02: Import growth data unavailable for VNM (year 2023)"
    ]
  }
}
```

---

## 10. `/health` 응답 내 DS-02 상태

```json
{
  "data_sources": {
    "DS-02": {
      "available": true,
      "last_snapshot": "2026-01-28",
      "record_count": 195,
      "year_range": "2021-2023",
      "indicators_collected": 7,
      "missing_rate": 0.03
    }
  }
}
```

---

## 11. 전체 Score 통합 위치 (5.4 연계)

DS-02의 `EconomicScore`는 최종 Score 산정(5.4)에서 다음과 같이 사용된다:

```text
FinalScore = 100 × (
    w_trade   × norm_trade_value      (DS-01)
  + w_econ    × EconomicScore          (DS-02) ← 여기
  - w_dist    × norm_distance          (DS-03)
  + w_contig  × contig_flag            (DS-03)
  + w_lang    × common_language_flag   (DS-03)
)
```

> **주의**: 위 통합 수식의 최종 가중치는 별도 "전체 Score 수식 통합본" 문서에서 확정한다.
> DS-02는 `EconomicScore` 하나의 값으로 합산되어 FinalScore에 투입된다.

---

## 12. 구현 체크리스트

- [ ] World Bank API 호출 모듈 구현 (7개 indicator code 고정)
- [ ] ISO3 → ISO2 매핑 테이블 구현
- [ ] 연도 선택 로직 구현 (max year, 3년 제약)
- [ ] 결측 시 국가 제외(GDP, Import) / 0점 처리(Growth, Inflation) 구분
- [ ] 이상값 판정 (GDP ≤ 0, Import < 0) → 제외 + warning
- [ ] 로그 정규화 수식 구현 (min-max on log scale)
- [ ] 클리핑 + 정규화 수식 구현 (3개 퍼센트 지표)
- [ ] EconomicScore 산식 구현 (가중치 5개 고정)
- [ ] 결과 min 0 클램핑
- [ ] 저장 스키마(WSB) JSON 구조 준수
- [ ] `/health` 응답에 DS-02 상태 반영
- [ ] `/predict` 응답에 economic_score, data_quality 반영
- [ ] 스냅샷 메타데이터 기록

---

## 13. 테스트 시나리오 (11장 연계)

### TC-DS02-001: 정상 수집 및 점수 산정
- **입력**: VNM, year=2023, 모든 지표 존재
- **기대**: economic_score 0 < x ≤ 1, missing_fields = []

### TC-DS02-002: 필수 지표 결측 → 후보군 제외
- **입력**: XXX, GDP=null
- **기대**: 해당 국가 results에서 제외, explanation에 warning

### TC-DS02-003: 선택 지표 결측 → 0점 처리
- **입력**: MMR, gdp_growth=null, inflation=null
- **기대**: economic_score 계산됨 (GDP, Import만으로), missing_fields에 기록

### TC-DS02-004: 3년 초과 데이터 → 무효
- **입력**: 국가 Y, 최신 GDP year=2020 (current=2026)
- **기대**: GDP 무효 → 후보군 제외

### TC-DS02-005: 이상값 (GDP ≤ 0)
- **입력**: 국가 Z, GDP=-100
- **기대**: 후보군 제외, warning 기록

### TC-DS02-006: 클리핑 경계값
- **입력**: GDP_growth=15% (upper=10)
- **기대**: clip → 10%, norm = (10+5)/15 = 1.0

### TC-DS02-007: EconomicScore 최소값 클램핑
- **입력**: 모든 양(+) 항목 0, Inflation max
- **기대**: score = max(0, -0.10) = 0

---

*문서 끝*
