"""
World Bank Data360 스타일 샘플 데이터 생성 및 클리닝
"""

import pandas as pd
import numpy as np
from datetime import datetime
import random

def generate_sample_worldbank_data(num_records=1000):
    """World Bank Data360 API 응답 구조를 모방한 샘플 데이터 생성"""
    print(f"\n{'='*60}")
    print(f"샘플 데이터 생성 중... ({num_records}개 레코드)")
    print(f"{'='*60}")

    # 국가 코드
    countries = ['USA', 'CHN', 'JPN', 'DEU', 'GBR', 'FRA', 'IND', 'BRA', 'CAN', 'KOR',
                 'ITA', 'AUS', 'ESP', 'MEX', 'IDN', 'NLD', 'SAU', 'TUR', 'CHE', 'POL']

    # 지표 코드
    indicators = [
        'NY.GDP.MKTP.CD',  # GDP (current US$)
        'SP.POP.TOTL',     # Population, total
        'NY.GDP.PCAP.CD',  # GDP per capita (current US$)
        'SP.URB.TOTL.IN.ZS',  # Urban population (% of total)
        'SE.PRM.ENRR',     # School enrollment, primary (% gross)
    ]

    # 연도
    years = list(range(2015, 2024))

    # 빈도
    frequencies = ['A']  # Annual

    # 데이터 생성
    data = []

    for _ in range(num_records):
        country = random.choice(countries)
        indicator = random.choice(indicators)
        year = random.choice(years)

        # 지표별 적절한 값 범위 설정
        if indicator == 'NY.GDP.MKTP.CD':  # GDP
            obs_value = np.random.uniform(1e11, 2e13)
        elif indicator == 'SP.POP.TOTL':  # Population
            obs_value = np.random.uniform(1e6, 1.5e9)
        elif indicator == 'NY.GDP.PCAP.CD':  # GDP per capita
            obs_value = np.random.uniform(1000, 80000)
        elif indicator == 'SP.URB.TOTL.IN.ZS':  # Urban %
            obs_value = np.random.uniform(20, 95)
        else:  # School enrollment
            obs_value = np.random.uniform(80, 105)

        # 일부 데이터를 NULL로 설정 (현실적인 데이터셋)
        if random.random() < 0.1:  # 10% 확률로 NULL
            obs_value = None

        record = {
            'DATABASE_ID': 'WB_WDI',
            'INDICATOR': indicator,
            'REF_AREA': country,
            'TIME_PERIOD': year,
            'OBS_VALUE': obs_value,
            'FREQ': random.choice(frequencies),
            'UNIT_MEASURE': 'USD' if 'NY.GDP' in indicator else 'Persons' if 'POP' in indicator else 'Percent',
            'UNIT_TYPE': 'Value',
            'UNIT_MULT': random.choice([0, 3, 6, 9]),
            'TIME_FORMAT': 'P1Y',
            'DECIMALS': 2,
            'OBS_STATUS': random.choice(['A', 'E', 'P', None]),  # Actual, Estimated, Provisional
            'OBS_CONF': random.choice(['F', None]),  # Free
            'DATA_SOURCE': 'World Bank',
            'LATEST_DATA': random.choice([True, False, None]),
            'COMMENT_OBS': None if random.random() < 0.95 else 'Estimated value',
            'COMMENT_TS': None,
            'AGG_METHOD': random.choice(['SUM', 'AVG', None]),
            'SEX': random.choice([None, 'M', 'F']) if random.random() < 0.2 else None,
            'AGE': None,
            'URBANISATION': None,
            'COMP_BREAKDOWN_1': None,
            'COMP_BREAKDOWN_2': None,
            'COMP_BREAKDOWN_3': None,
        }

        data.append(record)

    df = pd.DataFrame(data)

    # 일부 중복 데이터 추가 (클리닝 테스트용)
    duplicates = df.sample(n=int(num_records * 0.05))
    df = pd.concat([df, duplicates], ignore_index=True)

    # 일부 컬럼에 공백 추가 (클리닝 테스트용)
    df['REF_AREA'] = df['REF_AREA'].apply(lambda x: f" {x} " if random.random() < 0.3 else x)

    print(f"✓ {len(df)}개 레코드 생성 완료 (중복 포함)")
    print(f"✓ {len(df.columns)}개 컬럼")

    return df

def clean_data(df):
    """데이터 클리닝"""
    print(f"\n{'='*60}")
    print(f"데이터 클리닝 시작...")
    print(f"{'='*60}")

    original_rows = len(df)
    original_cols = len(df.columns)

    # 복사본 생성
    df_clean = df.copy()

    # 1. 컬럼명 정리
    df_clean.columns = df_clean.columns.str.strip()
    print(f"✓ 컬럼명 공백 제거")

    # 2. OBS_VALUE가 없는 행 제거
    if 'OBS_VALUE' in df_clean.columns:
        before = len(df_clean)
        df_clean = df_clean.dropna(subset=['OBS_VALUE'])
        removed = before - len(df_clean)
        print(f"✓ OBS_VALUE가 없는 {removed}개 행 제거")

    # 3. 중복 행 제거
    before = len(df_clean)
    df_clean = df_clean.drop_duplicates()
    removed = before - len(df_clean)
    print(f"✓ 중복 {removed}개 행 제거")

    # 4. 모든 값이 NULL인 컬럼 제거
    null_cols = df_clean.columns[df_clean.isnull().all()].tolist()
    if null_cols:
        df_clean = df_clean.drop(columns=null_cols)
        print(f"✓ 모두 NULL인 {len(null_cols)}개 컬럼 제거: {null_cols}")

    # 5. 거의 모든 값이 NULL인 컬럼 제거 (95% 이상)
    null_threshold = 0.95
    high_null_cols = []
    for col in df_clean.columns:
        null_ratio = df_clean[col].isnull().sum() / len(df_clean)
        if null_ratio > null_threshold:
            high_null_cols.append(col)

    if high_null_cols:
        df_clean = df_clean.drop(columns=high_null_cols)
        print(f"✓ 95% 이상 NULL인 {len(high_null_cols)}개 컬럼 제거: {high_null_cols}")

    # 6. TIME_PERIOD를 숫자로 변환
    if 'TIME_PERIOD' in df_clean.columns:
        df_clean['TIME_PERIOD'] = pd.to_numeric(df_clean['TIME_PERIOD'], errors='coerce')
        print(f"✓ TIME_PERIOD 형식 정리")

    # 7. OBS_VALUE를 숫자로 변환
    if 'OBS_VALUE' in df_clean.columns:
        df_clean['OBS_VALUE'] = pd.to_numeric(df_clean['OBS_VALUE'], errors='coerce')
        print(f"✓ OBS_VALUE를 숫자형으로 변환")

    # 8. 텍스트 컬럼 공백 제거
    text_columns = df_clean.select_dtypes(include=['object']).columns
    for col in text_columns:
        if df_clean[col].dtype == 'object':
            # None이 아닌 값만 strip 적용
            df_clean[col] = df_clean[col].apply(lambda x: x.strip() if isinstance(x, str) else x)
    print(f"✓ 텍스트 컬럼 {len(text_columns)}개의 공백 제거")

    # 9. UNIT_MULT를 숫자로 변환
    if 'UNIT_MULT' in df_clean.columns:
        df_clean['UNIT_MULT'] = pd.to_numeric(df_clean['UNIT_MULT'], errors='coerce')
        print(f"✓ UNIT_MULT 형식 정리")

    # 10. 이상치 제거 (OBS_VALUE가 음수인 경우 등)
    if 'OBS_VALUE' in df_clean.columns:
        before = len(df_clean)
        df_clean = df_clean[df_clean['OBS_VALUE'] >= 0]
        removed = before - len(df_clean)
        if removed > 0:
            print(f"✓ 음수 OBS_VALUE {removed}개 행 제거")

    # 11. 정렬 (TIME_PERIOD, REF_AREA, INDICATOR 기준)
    sort_cols = []
    if 'TIME_PERIOD' in df_clean.columns:
        sort_cols.append('TIME_PERIOD')
    if 'REF_AREA' in df_clean.columns:
        sort_cols.append('REF_AREA')
    if 'INDICATOR' in df_clean.columns:
        sort_cols.append('INDICATOR')

    if sort_cols:
        df_clean = df_clean.sort_values(by=sort_cols)
        print(f"✓ 데이터 정렬 완료: {sort_cols}")

    # 12. 인덱스 재설정
    df_clean = df_clean.reset_index(drop=True)
    print(f"✓ 인덱스 재설정")

    print(f"\n{'='*60}")
    print(f"클리닝 결과:")
    print(f"  - 원본: {original_rows}행 × {original_cols}컬럼")
    print(f"  - 클리닝 후: {len(df_clean)}행 × {len(df_clean.columns)}컬럼")
    print(f"  - 제거된 행: {original_rows - len(df_clean)} ({(original_rows - len(df_clean)) / original_rows * 100:.1f}%)")
    print(f"  - 제거된 컬럼: {original_cols - len(df_clean.columns)}")
    print(f"{'='*60}\n")

    return df_clean

def generate_data_summary(df):
    """데이터 요약 정보 생성"""
    print(f"\n{'='*60}")
    print(f"데이터 요약")
    print(f"{'='*60}")

    print(f"\n기본 정보:")
    print(f"  - 총 레코드 수: {len(df):,}")
    print(f"  - 총 컬럼 수: {len(df.columns)}")
    print(f"  - 메모리 사용량: {df.memory_usage(deep=True).sum() / 1024:.2f} KB")

    # 주요 컬럼 정보
    if 'TIME_PERIOD' in df.columns:
        print(f"\n시간 정보:")
        print(f"  - 기간: {int(df['TIME_PERIOD'].min())} ~ {int(df['TIME_PERIOD'].max())}")
        print(f"  - 연도 수: {df['TIME_PERIOD'].nunique()}")

    if 'REF_AREA' in df.columns:
        print(f"\n국가 정보:")
        print(f"  - 국가 수: {df['REF_AREA'].nunique()}")
        print(f"  - 국가 목록 (상위 10개): {', '.join(df['REF_AREA'].value_counts().head(10).index.tolist())}")

    if 'INDICATOR' in df.columns:
        print(f"\n지표 정보:")
        print(f"  - 지표 수: {df['INDICATOR'].nunique()}")
        for indicator in df['INDICATOR'].unique():
            count = (df['INDICATOR'] == indicator).sum()
            print(f"    - {indicator}: {count:,}개 레코드")

    if 'OBS_VALUE' in df.columns:
        print(f"\n관측값 통계:")
        print(f"  - 평균: {df['OBS_VALUE'].mean():,.2f}")
        print(f"  - 중앙값: {df['OBS_VALUE'].median():,.2f}")
        print(f"  - 최소: {df['OBS_VALUE'].min():,.2f}")
        print(f"  - 최대: {df['OBS_VALUE'].max():,.2f}")
        print(f"  - 표준편차: {df['OBS_VALUE'].std():,.2f}")

    # 결측치 정보
    null_counts = df.isnull().sum()
    has_nulls = null_counts[null_counts > 0]
    if len(has_nulls) > 0:
        print(f"\n결측치 현황:")
        for col, count in has_nulls.items():
            percentage = (count / len(df)) * 100
            print(f"  - {col}: {count:,}개 ({percentage:.1f}%)")
    else:
        print(f"\n결측치: 없음")

    # 데이터 타입
    print(f"\n데이터 타입:")
    for dtype in df.dtypes.unique():
        cols = df.select_dtypes(include=[dtype]).columns.tolist()
        print(f"  - {dtype}: {len(cols)}개 컬럼")

    print(f"{'='*60}\n")

def save_to_files(df_raw, df_clean, prefix="worldbank_data"):
    """원본과 클리닝된 데이터를 파일로 저장"""
    print(f"\n{'='*60}")
    print(f"파일 저장 중...")
    print(f"{'='*60}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 1. 원본 CSV 저장
    raw_csv = f"{prefix}_raw_{timestamp}.csv"
    df_raw.to_csv(raw_csv, index=False, encoding='utf-8-sig')
    print(f"✓ 원본 CSV 저장: {raw_csv}")

    # 2. 클리닝 CSV 저장
    clean_csv = f"{prefix}_clean_{timestamp}.csv"
    df_clean.to_csv(clean_csv, index=False, encoding='utf-8-sig')
    print(f"✓ 클리닝 CSV 저장: {clean_csv}")

    # 3. Excel 저장 (여러 시트)
    excel_file = f"{prefix}_{timestamp}.xlsx"
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        # 클리닝된 데이터
        df_clean.to_excel(writer, sheet_name='Clean_Data', index=False)

        # 원본 데이터
        df_raw.to_excel(writer, sheet_name='Raw_Data', index=False)

        # 요약 정보
        summary_data = [
            ['항목', '원본', '클리닝 후'],
            ['레코드 수', len(df_raw), len(df_clean)],
            ['컬럼 수', len(df_raw.columns), len(df_clean.columns)],
            ['제거된 행', len(df_raw) - len(df_clean), '-'],
            ['제거율 (%)', f"{((len(df_raw) - len(df_clean)) / len(df_raw) * 100):.1f}%", '-'],
            ['생성 일시', timestamp, timestamp],
        ]
        summary_df = pd.DataFrame(summary_data[1:], columns=summary_data[0])
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

        # 컬럼 설명
        column_info = []
        for col in df_clean.columns:
            column_info.append({
                '컬럼명': col,
                '데이터 타입': str(df_clean[col].dtype),
                '결측치 수': df_clean[col].isnull().sum(),
                '고유값 수': df_clean[col].nunique(),
                '샘플 값': str(df_clean[col].iloc[0]) if len(df_clean) > 0 else ''
            })
        col_df = pd.DataFrame(column_info)
        col_df.to_excel(writer, sheet_name='Column_Info', index=False)

    print(f"✓ Excel 파일 저장: {excel_file}")
    print(f"  - Clean_Data 시트: 클리닝된 데이터")
    print(f"  - Raw_Data 시트: 원본 데이터")
    print(f"  - Summary 시트: 요약 정보")
    print(f"  - Column_Info 시트: 컬럼 설명")

    print(f"{'='*60}\n")

    return raw_csv, clean_csv, excel_file

def main():
    """메인 실행 함수"""
    print(f"\n{'#'*60}")
    print(f"# World Bank Data360 스타일 샘플 데이터 생성 및 클리닝")
    print(f"{'#'*60}\n")

    # 1. 샘플 데이터 생성
    df_raw = generate_sample_worldbank_data(num_records=1000)

    print(f"\n원본 데이터 미리보기 (처음 10행):")
    print(df_raw.head(10))
    print(f"\n원본 데이터 컬럼 목록:")
    for i, col in enumerate(df_raw.columns, 1):
        print(f"  {i:2d}. {col}")

    # 2. 데이터 클리닝
    df_clean = clean_data(df_raw)

    # 3. 데이터 요약
    generate_data_summary(df_clean)

    # 4. 파일 저장
    raw_csv, clean_csv, excel_file = save_to_files(df_raw, df_clean, prefix="worldbank")

    # 5. 최종 결과 미리보기
    print(f"\n{'='*60}")
    print(f"클리닝된 데이터 미리보기 (처음 10행):")
    print(f"{'='*60}\n")
    print(df_clean.head(10).to_string())

    print(f"\n{'='*60}")
    print(f"클리닝된 데이터 통계:")
    print(f"{'='*60}\n")
    print(df_clean.describe())

    print(f"\n{'#'*60}")
    print(f"# 완료!")
    print(f"# 생성된 파일:")
    print(f"#   1. {raw_csv} (원본 CSV)")
    print(f"#   2. {clean_csv} (클리닝 CSV)")
    print(f"#   3. {excel_file} (통합 Excel)")
    print(f"{'#'*60}\n")

if __name__ == "__main__":
    main()
