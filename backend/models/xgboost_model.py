"""
XGBoost Model for Export Prediction
머신러닝 기반 수출액 예측 + SHAP 설명
"""

import numpy as np
import xgboost as xgb
import shap
from typing import Dict, List, Tuple


class XGBoostModel:
    """
    XGBoost 기반 수출액 예측 모델

    Features:
    - Gravity Model 예측값
    - GDP 성장률
    - 물류 성과 지수 (LPI)
    - 관세율
    - 문화 유사성 지수
    - 규제 편의성 지수
    """

    def __init__(self):
        self.model = xgb.XGBRegressor(
            objective='reg:squarederror',
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )

        self.explainer = None
        self.is_trained = False

        self.feature_names = [
            'gravity_pred',      # 중력모형 예측값
            'gdp_growth',        # GDP 성장률 (%)
            'lpi_score',         # 물류 성과 지수 (1-5)
            'tariff_rate',       # 관세율 (%)
            'culture_index',     # 문화 유사성 (0-100)
            'regulation_index'   # 규제 편의성 (0-100)
        ]

    def train(self, X: np.ndarray, y: np.ndarray):
        """
        모델 학습

        Args:
            X: Feature matrix [gravity_pred, gdp_growth, lpi_score, tariff_rate, culture_index, regulation_index]
            y: 실제 수출액 (USD)
        """
        self.model.fit(X, y)
        self.is_trained = True

        # SHAP Explainer 초기화
        self.explainer = shap.TreeExplainer(self.model)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        수출액 예측

        Args:
            X: Feature matrix

        Returns:
            예측된 수출액 (USD)
        """
        if not self.is_trained:
            # 학습되지 않은 경우 간단한 휴리스틱 사용
            return self._heuristic_predict(X)

        return self.model.predict(X)

    def _heuristic_predict(self, X: np.ndarray) -> np.ndarray:
        """
        학습되지 않은 경우 사용하는 휴리스틱 예측

        공식:
        Export = gravity_pred × (1 + gdp_growth/100) × (lpi_score/3) ×
                 (1 - tariff_rate/100) × (culture_index/100) × (regulation_index/100)
        """
        predictions = []

        for features in X:
            gravity_pred = features[0]
            gdp_growth = features[1]
            lpi_score = features[2]
            tariff_rate = features[3]
            culture_index = features[4]
            regulation_index = features[5]

            # 각 요인의 영향 계산
            growth_factor = 1 + (gdp_growth / 100)
            lpi_factor = lpi_score / 3.0
            tariff_factor = max(0.5, 1 - (tariff_rate / 100))
            culture_factor = culture_index / 100
            regulation_factor = regulation_index / 100

            # 최종 예측
            predicted_export = (
                gravity_pred *
                growth_factor *
                lpi_factor *
                tariff_factor *
                culture_factor *
                regulation_factor
            )

            predictions.append(predicted_export)

        return np.array(predictions)

    def explain(self, X: np.ndarray) -> Dict[str, any]:
        """
        SHAP을 이용한 예측 설명

        Args:
            X: Feature matrix (단일 샘플 또는 배치)

        Returns:
            {
                'shap_values': SHAP 값,
                'base_value': 기준 값,
                'feature_importance': 특성 중요도
            }
        """
        if not self.is_trained or self.explainer is None:
            # 휴리스틱 중요도
            return self._heuristic_explain(X)

        # SHAP 값 계산
        shap_values = self.explainer.shap_values(X)

        # 특성 중요도 계산
        feature_importance = dict(zip(
            self.feature_names,
            np.abs(shap_values).mean(axis=0)
        ))

        return {
            'shap_values': shap_values.tolist(),
            'base_value': self.explainer.expected_value,
            'feature_importance': feature_importance
        }

    def _heuristic_explain(self, X: np.ndarray) -> Dict[str, any]:
        """학습되지 않은 경우의 휴리스틱 설명"""
        # 각 특성의 상대적 중요도 (경험적 가중치)
        importance_weights = {
            'gravity_pred': 0.35,
            'gdp_growth': 0.15,
            'lpi_score': 0.20,
            'tariff_rate': 0.10,
            'culture_index': 0.10,
            'regulation_index': 0.10
        }

        return {
            'shap_values': None,
            'base_value': 0,
            'feature_importance': importance_weights
        }

    def get_feature_importance(self) -> Dict[str, float]:
        """특성 중요도 반환"""
        if not self.is_trained:
            return self._heuristic_explain(None)['feature_importance']

        importance = self.model.feature_importances_
        return dict(zip(self.feature_names, importance))

    def save_model(self, path: str):
        """모델 저장"""
        self.model.save_model(path)

    def load_model(self, path: str):
        """모델 로드"""
        self.model.load_model(path)
        self.is_trained = True
        self.explainer = shap.TreeExplainer(self.model)


# 테스트용 예제
if __name__ == "__main__":
    model = XGBoostModel()

    # 더미 데이터 생성
    X_train = np.random.rand(100, 6) * 100
    y_train = X_train[:, 0] * 1_000_000  # gravity_pred 기반

    # 학습
    print("모델 학습 중...")
    model.train(X_train, y_train)

    # 예측
    X_test = np.array([[80, 5.5, 3.8, 7.5, 85, 75]])
    prediction = model.predict(X_test)
    print(f"예측 수출액: ${prediction[0]:,.2f}")

    # 설명
    explanation = model.explain(X_test)
    print("\n특성 중요도:")
    for feature, importance in explanation['feature_importance'].items():
        print(f"  {feature}: {importance:.4f}")
