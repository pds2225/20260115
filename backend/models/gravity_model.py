"""
Gravity Model for Trade Prediction
경제학 기반 중력모형 - 국가 간 무역 예측
"""

import numpy as np
from sklearn.linear_model import LinearRegression
from typing import Dict, List


class GravityModel:
    """
    중력모형 (Gravity Model of Trade)

    이론적 배경:
    Trade_ij = (GDP_i × GDP_j) / Distance_ij^β

    실제 구현:
    log(Trade) = β₀ + β₁×log(GDP_target) - β₂×log(Distance) + β₃×FTA + β₄×LPI - β₅×Tariff
    """

    def __init__(self):
        self.model = LinearRegression()
        self.is_trained = False

        # 이론적 계수 (실제 무역 데이터 기반)
        self.coefficients = {
            'gdp': 0.85,        # GDP 탄력성
            'distance': -0.95,  # 거리 탄력성 (음수)
            'fta': 0.45,        # FTA 효과
            'lpi': 0.35,        # 물류 효과
            'tariff': -0.28     # 관세 효과 (음수)
        }

    def calculate_score(self, country_data: Dict) -> float:
        """
        중력모형 점수 계산

        Args:
            country_data: {
                'gdp': float,       # 10억 USD
                'distance': float,  # km
                'fta': bool,        # FTA 체결 여부
                'lpi': float,       # Logistics Performance Index (1-5)
                'tariff': float     # 관세율 (%)
            }

        Returns:
            float: 무역 잠재력 점수 (0-100)
        """
        # GDP 효과 (로그 스케일)
        gdp_effect = np.log1p(country_data['gdp']) * self.coefficients['gdp']

        # 거리 효과 (로그 스케일, 음수)
        distance_effect = np.log1p(country_data['distance']) * self.coefficients['distance']

        # FTA 효과
        fta_effect = self.coefficients['fta'] if country_data['fta'] else 0

        # 물류 효과
        lpi_effect = country_data['lpi'] * self.coefficients['lpi']

        # 관세 효과 (음수)
        tariff_effect = country_data['tariff'] * self.coefficients['tariff']

        # 총합 계산
        raw_score = gdp_effect + distance_effect + fta_effect + lpi_effect + tariff_effect

        # 0-100 스케일로 정규화
        normalized_score = self._normalize_score(raw_score)

        return normalized_score

    def _normalize_score(self, raw_score: float) -> float:
        """점수를 0-100 범위로 정규화"""
        # 시그모이드 함수 사용
        sigmoid = 100 / (1 + np.exp(-raw_score / 2))
        return float(sigmoid)

    def train(self, X: np.ndarray, y: np.ndarray):
        """
        실제 무역 데이터로 모델 학습

        Args:
            X: Feature matrix [GDP, Distance, FTA, LPI, Tariff]
            y: 실제 무역액 (로그 스케일)
        """
        self.model.fit(X, y)
        self.is_trained = True

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        학습된 모델로 예측

        Args:
            X: Feature matrix

        Returns:
            예측된 무역액 (로그 스케일)
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        return self.model.predict(X)

    def get_feature_importance(self) -> Dict[str, float]:
        """특성 중요도 반환"""
        if not self.is_trained:
            return self.coefficients

        return {
            'gdp': abs(self.model.coef_[0]),
            'distance': abs(self.model.coef_[1]),
            'fta': abs(self.model.coef_[2]),
            'lpi': abs(self.model.coef_[3]),
            'tariff': abs(self.model.coef_[4])
        }


# 테스트용 예제
if __name__ == "__main__":
    model = GravityModel()

    # 베트남 예제
    vietnam_data = {
        'gdp': 366.0,
        'distance': 2400,
        'fta': True,
        'lpi': 3.3,
        'tariff': 5.2
    }

    score = model.calculate_score(vietnam_data)
    print(f"베트남 무역 잠재력 점수: {score:.2f}/100")

    # 미국 예제
    usa_data = {
        'gdp': 25462.0,
        'distance': 11000,
        'fta': True,
        'lpi': 3.9,
        'tariff': 8.5
    }

    score = model.calculate_score(usa_data)
    print(f"미국 무역 잠재력 점수: {score:.2f}/100")
