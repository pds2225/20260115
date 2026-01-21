"""
World Bank Data360 API - 데이터 다운로드 및 클리닝 스크립트
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import json
import sys

# API 기본 설정
BASE_URL = "https://data360api.worldbank.org"
DATASET_ID = "WB_WDI"  # World Development Indicators

def get_indicators(dataset_id):
    """데이터셋의 지표 목록 조회"""
    print(f"\n{'='*60}")
    print(f"데이터셋 '{dataset_id}'의 지표 목록 조회 중...")
    print(f"{'='*60}")

    url = f"{BASE_URL}/data360/indicators"
    params = {"datasetId": dataset_id}

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        indicators = response.json()

        print(f"\n✓ {len(indicators)}개의 지표를 찾았습니다.")
        print(f"\n처음 10개 지표:")
        for i, indicator in enumerate(indicators[:10], 1):
            print(f"  {i}. {indicator}")

        return indicators
    except Exception as e:
        print(f"✗ 오류 발생: {str(e)}")
        return []

def fetch_data(database_id, indicator=None, ref_area=None, time_from=None, time_to=None, limit=1000):
    """API에서 데이터 가져오기"""
    print(f"\n{'='*60}")
    print(f"데이터 다운로드 중...")
    print(f"{'='*60}")

    url = f"{BASE_URL}/data360/data"
    params = {
        "DATABASE_ID": database_id,
        "skip": 0
    }

    if indicator:
        params["INDICATOR"] = indicator
    if ref_area:
        params["REF_AREA"] = ref_area
    if time_from:
        params["timePeriodFrom"] = time_from
    if time_to:
        params["timePeriodTo"] = time_to

    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        print(f"✓ {len(data)}개의 레코드를 다운로드했습니다.")

        # JSON 데이터를 DataFrame으로 변환
        df = pd.DataFrame(data)

        print(f"\n데이터 구조:")
        print(f"  - 행 개수: {len(df)}")
        print(f"  - 컬럼 개수: {len(df.columns)}")
        print(f"\n컬럼 목록:")
        for i, col in enumerate(df.columns, 1):
            print(f"  {i}. {col}")

        return df
    except Exception as e:
        print(f"✗ 오류 발생: {str(e)}")
        return pd.DataFrame()

def clean_data(df):
    """데이터 클리닝"""
    print(f"\n{'='*60}")
    print(f"데이터 클리닝 시작...")
    print(f"{'='*60}")

    original_rows = len(df)
    original_cols = len(df.columns)

    # 1. 복사본 생성
    df_clean = df.copy()

    # 2. 컬럼명 정리 (공백 제거)
    df_clean.columns = df_clean.columns.str.strip()

    # 3. OBS_VALUE가 없는 행 제거 (핵심 데이터)
    if 'OBS_VALUE' in df_clean.columns:
        before = len(df_clean)
        df_clean = df_clean.dropna(subset=['OBS_VALUE'])
        removed = before - len(df_clean)
        print(f"✓ OBS_VALUE가 없는 {removed}개 행 제거")

    # 4. 중복 행 제거
    before = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    removed = before - len(df_clean)
    print(f"✓ 중복 {removed}개 행 제거")

    # 5. 불필요한 컬럼 제거 (모든 값이 NULL인 컬럼)
    null_cols = df_clean.columns[df_clean.isnull().all()].tolist()
    if null_cols:
        df_clean = df_clean.drop(columns=null_cols)
        print(f"✓ 모두 NULL인 {len(null_cols)}개 컬럼 제거: {null_cols}")

    # 6. TIME_PERIOD를 숫자로 변환 (가능한 경우)
    if 'TIME_PERIOD' in df_clean.columns:
        df_clean['TIME_PERIOD'] = pd.to_numeric(df_clean['TIME_PERIOD'], errors='ignore')
        print(f"✓ TIME_PERIOD 형식 정리")

    # 7. OBS_VALUE를 숫자로 변환
    if 'OBS_VALUE' in df_clean.columns:
        df_clean['OBS_VALUE'] = pd.to_numeric(df_clean['OBS_VALUE'], errors='coerce')
        print(f"✓ OBS_VALUE를 숫자형으로 변환")

    # 8. 텍스트 컬럼 공백 제거
    text_columns = df_clean.select_dtypes(include=['object']).columns
    for col in text_columns:
        df_clean[col] = df_clean[col].str.strip() if df_clean[col].dtype == 'object' else df_clean[col]
    print(f"✓ 텍스트 컬럼 공백 제거")

    # 9. 정렬 (TIME_PERIOD, REF_AREA 기준)
    sort_cols = []
    if 'TIME_PERIOD' in df_clean.columns:
        sort_cols.append('TIME_PERIOD')
    if 'REF_AREA' in df_clean.columns:
        sort_cols.append('REF_AREA')
    if sort_cols:
        df_clean = df_clean.sort_values(by=sort_cols)
        print(f"✓ 데이터 정렬 완료: {sort_cols}")

    # 10. 인덱스 재설정
    df_clean = df_clean.reset_index(drop=True)

    print(f"\n{'='*60}")
    print(f"클리닝 결과:")
    print(f"  - 원본: {original_rows}행 × {original_cols}컬럼")
    print(f"  - 클리닝 후: {len(df_clean)}행 × {len(df_clean.columns)}컬럼")
    print(f"  - 제거된 행: {original_rows - len(df_clean)}")
    print(f"  - 제거된 컬럼: {original_cols - len(df_clean.columns)}")
    print(f"{'='*60}\n")

    return df_clean

def generate_data_summary(df):
    """데이터 요약 정보 생성"""
    print(f"\n{'='*60}")
    print(f"데이터 요약")
    print(f"{'='*60}")

    summary = {
        "총 레코드 수": len(df),
        "총 컬럼 수": len(df.columns),
        "생성 일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # 주요 컬럼 정보
    if 'TIME_PERIOD' in df.columns:
        summary["시간 범위"] = f"{df['TIME_PERIOD'].min()} ~ {df['TIME_PERIOD'].max()}"

    if 'REF_AREA' in df.columns:
        summary["국가 수"] = df['REF_AREA'].nunique()

    if 'INDICATOR' in df.columns:
        summary["지표 수"] = df['INDICATOR'].nunique()

    if 'OBS_VALUE' in df.columns:
        summary["관측값 통계"] = {
            "평균": float(df['OBS_VALUE'].mean()) if not df['OBS_VALUE'].isna().all() else None,
            "최소": float(df['OBS_VALUE'].min()) if not df['OBS_VALUE'].isna().all() else None,
            "최대": float(df['OBS_VALUE'].max()) if not df['OBS_VALUE'].isna().all() else None
        }

    # 결측치 정보
    null_counts = df.isnull().sum()
    summary["결측치 현황"] = {col: int(count) for col, count in null_counts.items() if count > 0}

    # 출력
    for key, value in summary.items():
        if isinstance(value, dict):
            print(f"\n{key}:")
            for k, v in value.items():
                print(f"  - {k}: {v}")
        else:
            print(f"  {key}: {value}")

    print(f"{'='*60}\n")

    return summary

def save_to_files(df, prefix="worldbank_data"):
    """데이터를 CSV와 Excel 파일로 저장"""
    print(f"\n{'='*60}")
    print(f"파일 저장 중...")
    print(f"{'='*60}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV 저장
    csv_filename = f"{prefix}_{timestamp}.csv"
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    print(f"✓ CSV 파일 저장: {csv_filename}")

    # Excel 저장
    excel_filename = f"{prefix}_{timestamp}.xlsx"
    with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Data', index=False)

        # 요약 시트 추가
        summary_df = pd.DataFrame([
            ["총 레코드 수", len(df)],
            ["총 컬럼 수", len(df.columns)],
            ["생성 일시", timestamp],
        ], columns=['항목', '값'])
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

    print(f"✓ Excel 파일 저장: {excel_filename}")
    print(f"{'='*60}\n")

    return csv_filename, excel_filename

def main():
    """메인 실행 함수"""
    print(f"\n{'#'*60}")
    print(f"# World Bank Data360 API - 데이터 다운로드 및 클리닝")
    print(f"{'#'*60}\n")

    # 1. 지표 목록 조회
    indicators = get_indicators(DATASET_ID)

    if not indicators:
        print("지표 목록을 가져올 수 없습니다. 프로그램을 종료합니다.")
        return

    # 2. 샘플 데이터 다운로드 (첫 번째 지표 사용)
    sample_indicator = indicators[0] if indicators else None

    print(f"\n샘플 지표로 '{sample_indicator}' 사용")

    df_raw = fetch_data(
        database_id=DATASET_ID,
        indicator=sample_indicator,
        time_from="2015",
        time_to="2023"
    )

    if df_raw.empty:
        print("데이터를 다운로드할 수 없습니다. 프로그램을 종료합니다.")
        return

    # 3. 데이터 클리닝
    df_clean = clean_data(df_raw)

    # 4. 데이터 요약
    summary = generate_data_summary(df_clean)

    # 5. 파일 저장
    csv_file, excel_file = save_to_files(df_clean, prefix="worldbank_clean")

    print(f"\n{'#'*60}")
    print(f"# 완료!")
    print(f"# - CSV: {csv_file}")
    print(f"# - Excel: {excel_file}")
    print(f"{'#'*60}\n")

    # 6. 샘플 데이터 미리보기
    print("샘플 데이터 (처음 5행):")
    print(df_clean.head())

if __name__ == "__main__":
    main()
