import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, Globe, TrendingUp, BarChart3, Shield, Zap } from 'lucide-react';
import { Link } from 'react-router-dom';

const LandingPage = () => {
  const features = [
    {
      icon: <Globe className="w-8 h-8" />,
      title: "글로벌 시장 분석",
      description: "200개 이상 국가의 무역 데이터를 실시간 분석"
    },
    {
      icon: <TrendingUp className="w-8 h-8" />,
      title: "AI 기반 예측",
      description: "중력모형과 머신러닝을 결합한 하이브리드 AI"
    },
    {
      icon: <BarChart3 className="w-8 h-8" />,
      title: "설명 가능한 AI",
      description: "SHAP 기술로 추천 근거를 6개 요인으로 설명"
    },
    {
      icon: <Shield className="w-8 h-8" />,
      title: "신뢰할 수 있는 데이터",
      description: "UN Comtrade, World Bank 등 공신력 있는 출처"
    },
    {
      icon: <Zap className="w-8 h-8" />,
      title: "빠른 분석",
      description: "Redis 캐싱으로 1,870배 빠른 응답 속도"
    },
    {
      icon: <BarChart3 className="w-8 h-8" />,
      title: "실시간 모니터링",
      description: "Prometheus + Grafana로 서비스 안정성 보장"
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <h1 className="text-5xl md:text-6xl font-bold text-gray-900 mb-6">
            수출 최적 국가를
            <span className="text-blue-600"> AI가 찾아드립니다</span>
          </h1>
          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            HS코드만 입력하면 경제학 이론과 머신러닝이 결합된 AI가
            최적의 수출 국가를 분석하고 그 이유를 설명해드립니다.
          </p>
          <Link to="/analysis">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="bg-blue-600 text-white px-8 py-4 rounded-lg text-lg font-semibold
                       flex items-center gap-2 mx-auto hover:bg-blue-700 transition-colors"
            >
              무료로 시작하기
              <ArrowRight className="w-5 h-5" />
            </motion.button>
          </Link>
        </motion.div>

        {/* Demo Image/Video Placeholder */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mt-16 max-w-5xl mx-auto"
        >
          <div className="bg-white rounded-2xl shadow-2xl p-8 border border-gray-200">
            <div className="aspect-video bg-gradient-to-br from-blue-100 to-purple-100 rounded-lg
                          flex items-center justify-center">
              <div className="text-center">
                <BarChart3 className="w-24 h-24 text-blue-600 mx-auto mb-4" />
                <p className="text-gray-600 text-lg">분석 결과 미리보기</p>
              </div>
            </div>
          </div>
        </motion.div>
      </section>

      {/* Features Section */}
      <section className="container mx-auto px-4 py-20">
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            왜 우리 서비스인가?
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            단순한 통계가 아닌, 경제학 이론과 최신 AI 기술이 결합된 분석
          </p>
        </motion.div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {features.map((feature, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: index * 0.1 }}
              viewport={{ once: true }}
              whileHover={{ y: -5 }}
              className="bg-white p-6 rounded-xl shadow-lg border border-gray-100 hover:shadow-xl transition-shadow"
            >
              <div className="text-blue-600 mb-4">{feature.icon}</div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">
                {feature.title}
              </h3>
              <p className="text-gray-600">{feature.description}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How It Works Section */}
      <section className="container mx-auto px-4 py-20 bg-white">
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            간단한 3단계
          </h2>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
          {[
            { step: "1", title: "HS코드 입력", desc: "수출하려는 제품의 HS코드 입력 또는 선택" },
            { step: "2", title: "AI 분석", desc: "중력모형 + XGBoost로 200개국 분석" },
            { step: "3", title: "결과 확인", desc: "추천 국가와 근거를 차트로 확인" }
          ].map((item, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, delay: index * 0.2 }}
              viewport={{ once: true }}
              className="text-center"
            >
              <div className="w-16 h-16 bg-blue-600 text-white rounded-full flex items-center
                           justify-center text-2xl font-bold mx-auto mb-4">
                {item.step}
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">{item.title}</h3>
              <p className="text-gray-600">{item.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="container mx-auto px-4 py-20">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          whileInView={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true }}
          className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-12 text-center text-white"
        >
          <h2 className="text-4xl font-bold mb-4">
            지금 바로 시작해보세요
          </h2>
          <p className="text-xl mb-8 opacity-90">
            회원가입 없이 무료로 이용 가능합니다
          </p>
          <Link to="/analysis">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="bg-white text-blue-600 px-8 py-4 rounded-lg text-lg font-semibold
                       hover:bg-gray-100 transition-colors"
            >
              무료 분석 시작하기
            </motion.button>
          </Link>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-white py-8">
        <div className="container mx-auto px-4 text-center">
          <p className="text-gray-400">
            © 2025 HS Code Export Analyzer. All rights reserved.
          </p>
          <p className="text-gray-500 mt-2 text-sm">
            Powered by Gravity Model + XGBoost + SHAP
          </p>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
