# DS-02 World Bank 데이터 수집·가공 명세 (WSB 기준)

> **문서 버전**: v1.1 (v1.0에서 실제 CSV 데이터 기반으로 수정)
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

## 2. 데이터 소스 (v1 확정: CSV 파일 2종)

### 2.1 파일 목록

| 파일명 | 지표 | 내부 필드명 | WB 표준 코드 |
|--------|------|-----------|-------------|
| `WB_WDI_NY_GDP_MKTP_CD.csv` | GDP (current USD) | `gdp_usd` | `NY.GDP.MKTP.CD` |
| `WB_WDI_NY_GDP_MKTP_KD_ZG.csv` | GDP growth (annual %) | `gdp_growth_pct` | `NY.GDP.MKTP.KD.ZG` |

> **위 2개 지표 외 World Bank 데이터는 v1 범위에서 사용 금지**

### 2.2 CSV 컬럼 구조

| CSV 컬럼 | 매핑 대상 | 설명 | 예시 |
|----------|----------|------|------|
| `REF_AREA` | `country_iso3` | ISO3 국가코드 (변환 불필요) | USA, KOR, VNM |
| `TIME_PERIOD` | `year` | 연도 (정수) | 2023 |
| `OBS_VALUE` | `value` | 관측값 | 27292000000000.0 |
| `INDICATOR` | (식별용) | CSV별 고정값 | WB_WDI_NY_GDP_MKTP_CD |
| `REF_AREA_LABEL` | `country_name` | 국가명 (참조) | United States |
| `UNIT_MEASURE` | (참조) | 단위 코드 | USD, PC_A |
| `OBS_STATUS` | (참조) | 관측 상태 | A (Normal) |

### 2.3 Indicator 코드 변환 규칙

```
CSV INDICATOR 컬럼         →  내부 필드명        →  WB 표준 코드
WB_WDI_NY_GDP_MKTP_CD     →  gdp_usd           →  NY.GDP.MKTP.CD
WB_WDI_NY_GDP_MKTP_KD_ZG  →  gdp_growth_pct    →  NY.GDP.MKTP.KD.ZG
```

변환 로직: `WB_WDI_` 접두사 제거 + `_` → `.`

### 2.4 데이터 통계 (참조)

| 항목 | GDP 파일 | GDP growth 파일 |
|------|----------|----------------|
| 총 레코드 | ~14,561 | ~14,133 |
| 국가/지역 수 | 262 | 262 |
| 연도 범위 | 1960~2024 | 1961~2024 |
| 단위 | current USD | % (연간) |

### 2.5 명시적 제외 항목 (Out of Scope)

- GDP per capita, Import value/growth, Inflation, Population (v2에서 확장 예정)
- 환율, 실업률, 제조업 비중, FDI, GNI, PPP, Governance Indicators

---

## 3. 데이터 선택 규칙

### 3.1 연도 선택

```text
target_year = max(year WHERE value IS NOT NULL)
제약: current_year - target_year ≤ 3
```

- 3년 초과 시 → 해당 지표 무효 (결측 처리)
- 국가별 연도 혼용 허용 (GDP와 GDP growth의 연도가 달라도 됨)

### 3.2 권장 기준 연도

- effective_year: **2024** 또는 **2023** (CSV 최신 데이터 기준)

---

## 4. 결측값·이상값 처리 규칙

### 4.1 GDP 결측/이상 → 후보군 제외

| 상황 | 처리 |
|------|------|
| GDP = null/NaN | 해당 국가 **후보군 제외** (Hard Filter) |
| GDP = 0 | **결측으로 간주** → 후보군 제외 |
| GDP < 0 | **이상값** → 후보군 제외 + warning |

### 4.2 GDP growth 결측 → 0점 처리

| 상황 | 처리 |
|------|------|
| GDP growth = null/NaN | 해당 항목 점수 = 0 (국가는 유지) |
| GDP growth = 0 | **유효한 0값** (결측 아님, 정상 처리) |

### 4.3 금지 사항

- 임의 대체(Imputation) 금지: 결측을 평균/중앙값으로 채우지 않는다

---

## 5. 정규화 규칙 (수식 고정)

### 5.1 GDP → 로그 스케일 min-max 정규화

```text
norm_gdp = (ln(gdp) - min_ln) / (max_ln - min_ln)
```

- `ln` = 자연로그
- `min_ln`, `max_ln`: 해당 스냅샷의 **유효 후보국 전체** 기준
- 결과 범위: 0 ~ 1
- 모든 값 동일 시: 0.5 반환

### 5.2 GDP growth → 클리핑 + 0-1 정규화

```text
Step 1: clipped = clip(gdp_growth, -5, +10)
Step 2: norm = (clipped - (-5)) / (10 - (-5)) = (clipped + 5) / 15
```

| 입력 | 클리핑 | 정규화 |
|------|--------|--------|
| -10% | -5% | 0.00 |
| -5% | -5% | 0.00 |
| 0% | 0% | 0.33 |
| 5% | 5% | 0.67 |
| 10% | 10% | 1.00 |
| 15% | 10% | 1.00 |

---

## 6. EconomicScore 산식 (v1 확정)

### 6.1 수식

```text
EconomicScore = 0.70 × norm(GDP) + 0.30 × norm_clip(GDP_growth)
```

### 6.2 가중치 표

| 항목 | 가중치 | 방향 | 의미 |
|------|--------|------|------|
| GDP | 0.70 | + | 시장 규모 |
| GDP growth | 0.30 | + | 성장성 보정 |
| **합계** | **1.00** | | |

### 6.3 결과 범위

- 이론적 범위: 0 ~ 1.0
- GDP growth 결측 시: 최대 0.70 (GDP만으로)
- **최소 0 적용**: `max(0, EconomicScore)`

---

## 7. 저장 스키마

### 7.1 레코드 예시

```json
{
  "country_iso3": "VNM",
  "country_name": "Vietnam",
  "year": 2023,
  "indicators": {
    "gdp_usd": 434000000000,
    "gdp_growth_pct": 5.07
  },
  "normalized": {
    "norm_gdp": 0.72,
    "norm_gdp_growth": 0.67
  },
  "economic_score": 0.70,
  "data_quality": {
    "missing_fields": [],
    "warnings": []
  }
}
```

---

## 8. API 응답 내 DS-02 반영

### 8.1 `/predict` score_components

```json
{
  "score_components": {
    "economic_score": 0.70
  }
}
```

### 8.2 `/predict` explanation

```json
{
  "explanation": {
    "top_factors": [
      {"factor": "gdp_usd", "direction": "positive", "source": "DS-02"},
      {"factor": "gdp_growth_pct", "direction": "positive", "source": "DS-02"}
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

### 8.3 `/health` DS-02 상태

```json
{
  "data_sources": {
    "DS-02": {
      "available": true,
      "last_snapshot": "2026-01-28",
      "record_count": 262,
      "year_range": "2021-2024",
      "indicators_collected": 2,
      "csv_files": [
        "WB_WDI_NY_GDP_MKTP_CD.csv",
        "WB_WDI_NY_GDP_MKTP_KD_ZG.csv"
      ]
    }
  }
}
```

---

## 9. 전체 Score 통합 위치 (5.4 연계)

DS-02의 `EconomicScore`는 최종 Score에서 하나의 항목으로 사용:

```text
FinalScore = 100 × (
    w_trade   × norm_trade_value      (DS-01)
  + w_econ    × EconomicScore          (DS-02) ← 여기
  - w_dist    × norm_distance          (DS-03)
  + w_contig  × contig_flag            (DS-03)
  + w_lang    × common_language_flag   (DS-03)
)
```

---

## 10. 구현 체크리스트

- [ ] CSV 로더 구현 (REF_AREA, TIME_PERIOD, OBS_VALUE 파싱)
- [ ] ISO3 코드 직접 사용 (ISO2 변환 불필요)
- [ ] 연도 선택 로직 구현 (max year, 3년 제약)
- [ ] GDP=0 → 결측 간주 처리
- [ ] GDP ≤ 0 → 이상값 → 후보군 제외 + warning
- [ ] GDP growth 결측 → 0점 처리 (국가 유지)
- [ ] 로그 정규화 수식 구현 (ln + min-max)
- [ ] 클리핑(-5~+10) + 0-1 정규화
- [ ] EconomicScore = 0.70*GDP + 0.30*Growth
- [ ] 결과 min 0 클램핑
- [ ] `/health` 응답에 DS-02 상태 반영
- [ ] `/predict` 응답에 economic_score, data_quality 반영

---

## 11. 테스트 시나리오

| ID | 시나리오 | 기대 결과 |
|----|---------|----------|
| TC-DS02-001 | 정상 (GDP+Growth 모두 존재) | 0 < economic_score ≤ 1 |
| TC-DS02-002 | GDP 결측 → 제외 | excluded=True |
| TC-DS02-003 | GDP=0 → 결측 간주 → 제외 | excluded=True |
| TC-DS02-004 | GDP < 0 → 이상값 → 제외 | excluded=True, warning |
| TC-DS02-005 | GDP growth 결측 → 0점 | excluded=False, score = GDP 기여분만 |
| TC-DS02-006 | Growth 클리핑 상한 (15%→10%) | norm = 1.0 |
| TC-DS02-007 | Growth 클리핑 하한 (-10%→-5%) | norm = 0.0 |
| TC-DS02-008 | 3년 초과 데이터 → 무효 | 해당 지표 결측 처리 |
| TC-DS02-009 | GDP가 큰 국가 → 높은 norm_gdp | USA > VNM |

---

## 12. 버전 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|---------|
| v1.0 | 2026-01-28 | 초안 (7개 지표, API 기반) |
| v1.1 | 2026-01-28 | **실제 CSV 데이터 기반으로 수정**: 2개 지표 확정, CSV 로더 전환, GDP=0 결측 규칙 반영, ISO2 변환 제거 |

---

*문서 끝*
