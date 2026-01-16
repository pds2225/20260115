import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, TrendingUp, DollarSign, Globe, Truck, Users, FileText, Loader2 } from 'lucide-react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
         BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const AnalysisPage = () => {
  const [hsCode, setHsCode] = useState('');
  const [topN, setTopN] = useState(5);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  // HS코드 빠른 선택 버튼
  const quickHsCodes = [
    { code: '33', name: '화장품', emoji: '💄' },
    { code: '85', name: '전자제품', emoji: '📱' },
    { code: '84', name: '기계류', emoji: '⚙️' },
    { code: '87', name: '자동차', emoji: '🚗' },
    { code: '61', name: '의류', emoji: '👕' },
    { code: '39', name: '플라스틱', emoji: '🧪' },
    { code: '90', name: '광학기기', emoji: '📷' },
    { code: '94', name: '가구', emoji: '🪑' }
  ];

  const handleAnalysis = async () => {
    if (!hsCode) {
      setError('HS코드를 입력해주세요');
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const response = await fetch('http://localhost:8000/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hs_code: hsCode,
          exporter_country: 'KOR',
          top_n: topN
        })
      });

      if (!response.ok) {
        throw new Error('서버 응답 오류');
      }

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(`분석 중 오류 발생: ${err.message}. 백엔드 서버가 실행 중인지 확인해주세요.`);

      // 데모용 더미 데이터
      setResults({
        top_countries: [
          {
            country: "베트남",
            country_code: "VNM",
            predicted_export: 245000000,
            gravity_score: 82.5,
            factors: {
              gdp_score: 85,
              distance_score: 90,
              fta_score: 100,
              lpi_score: 75,
              tariff_score: 80,
              culture_score: 88
            }
          },
          {
            country: "미국",
            country_code: "USA",
            predicted_export: 198000000,
            gravity_score: 78.3,
            factors: {
              gdp_score: 100,
              distance_score: 45,
              fta_score: 100,
              lpi_score: 95,
              tariff_score: 70,
              culture_score: 65
            }
          },
          {
            country: "일본",
            country_code: "JPN",
            predicted_export: 167000000,
            gravity_score: 76.8,
            factors: {
              gdp_score: 95,
              distance_score: 95,
              fta_score: 0,
              lpi_score: 98,
              tariff_score: 65,
              culture_score: 92
            }
          },
          {
            country: "중국",
            country_code: "CHN",
            predicted_export: 152000000,
            gravity_score: 74.2,
            factors: {
              gdp_score: 100,
              distance_score: 92,
              fta_score: 100,
              lpi_score: 80,
              tariff_score: 60,
              culture_score: 85
            }
          },
          {
            country: "태국",
            country_code: "THA",
            predicted_export: 128000000,
            gravity_score: 71.5,
            factors: {
              gdp_score: 70,
              distance_score: 88,
              fta_score: 100,
              lpi_score: 78,
              tariff_score: 75,
              culture_score: 80
            }
          }
        ],
        explanation: {
          primary_factors: ["gdp_score", "fta_score", "distance_score"],
          insights: [
            "FTA 체결 국가가 높은 순위를 차지",
            "지리적 근접성이 중요한 요소",
            "물류 인프라가 우수한 국가 선호"
          ]
        }
      });
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 1
    }).format(value);
  };

  const getRadarData = (factors) => {
    return [
      { subject: 'GDP', value: factors.gdp_score, fullMark: 100 },
      { subject: '거리', value: factors.distance_score, fullMark: 100 },
      { subject: 'FTA', value: factors.fta_score, fullMark: 100 },
      { subject: '물류', value: factors.lpi_score, fullMark: 100 },
      { subject: '관세', value: factors.tariff_score, fullMark: 100 },
      { subject: '문화', value: factors.culture_score, fullMark: 100 }
    ];
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 py-8">
      <div className="container mx-auto px-4">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            수출 국가 분석
          </h1>
          <p className="text-gray-600">
            HS코드를 입력하면 AI가 최적의 수출 국가를 추천합니다
          </p>
        </motion.div>

        {/* Input Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-xl shadow-lg p-6 mb-8"
        >
          {/* 빠른 선택 버튼 */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              빠른 선택
            </label>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
              {quickHsCodes.map((item) => (
                <motion.button
                  key={item.code}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={() => setHsCode(item.code)}
                  className={`p-3 rounded-lg border-2 transition-all ${
                    hsCode === item.code
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-blue-300'
                  }`}
                >
                  <div className="text-2xl mb-1">{item.emoji}</div>
                  <div className="text-xs font-medium text-gray-700">{item.name}</div>
                  <div className="text-xs text-gray-500">HS {item.code}</div>
                </motion.button>
              ))}
            </div>
          </div>

          {/* 직접 입력 */}
          <div className="grid md:grid-cols-3 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                HS코드 입력
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={hsCode}
                  onChange={(e) => setHsCode(e.target.value)}
                  placeholder="예: 33 (화장품), 85 (전자제품)"
                  className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:border-blue-500
                           focus:outline-none transition-colors"
                />
                <Search className="absolute right-3 top-3.5 text-gray-400 w-5 h-5" />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                추천 국가 수
              </label>
              <select
                value={topN}
                onChange={(e) => setTopN(Number(e.target.value))}
                className="w-full px-4 py-3 border-2 border-gray-300 rounded-lg focus:border-blue-500
                         focus:outline-none transition-colors"
              >
                <option value={3}>상위 3개국</option>
                <option value={5}>상위 5개국</option>
                <option value={10}>상위 10개국</option>
              </select>
            </div>
          </div>

          {/* 분석 버튼 */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={handleAnalysis}
            disabled={loading}
            className="w-full mt-6 bg-blue-600 text-white py-4 rounded-lg font-semibold
                     hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed
                     flex items-center justify-center gap-2 transition-colors"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                분석 중...
              </>
            ) : (
              <>
                <TrendingUp className="w-5 h-5" />
                분석 시작
              </>
            )}
          </motion.button>

          {/* 에러 메시지 */}
          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg"
            >
              <p className="text-yellow-800 text-sm">{error}</p>
              <p className="text-yellow-600 text-xs mt-1">
                데모 데이터로 표시됩니다.
              </p>
            </motion.div>
          )}
        </motion.div>

        {/* Results Section */}
        <AnimatePresence>
          {results && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* 국가 카드 */}
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {results.top_countries.map((country, index) => (
                  <motion.div
                    key={country.country_code}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: index * 0.1 }}
                    className="bg-white rounded-xl shadow-lg p-6 border-2 border-gray-200
                             hover:border-blue-500 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <div className="text-sm text-gray-500 mb-1">#{index + 1} 추천</div>
                        <h3 className="text-2xl font-bold text-gray-900">
                          {country.country}
                        </h3>
                        <p className="text-gray-500 text-sm">{country.country_code}</p>
                      </div>
                      <div className="text-right">
                        <div className="text-3xl font-bold text-blue-600">
                          {country.gravity_score.toFixed(1)}
                        </div>
                        <div className="text-xs text-gray-500">점수</div>
                      </div>
                    </div>

                    <div className="mb-4 p-3 bg-blue-50 rounded-lg">
                      <div className="text-sm text-gray-600 mb-1">예상 수출액</div>
                      <div className="text-2xl font-bold text-blue-600">
                        {formatCurrency(country.predicted_export)}
                      </div>
                    </div>

                    {/* 미니 레이더 차트 */}
                    <div className="h-48">
                      <ResponsiveContainer width="100%" height="100%">
                        <RadarChart data={getRadarData(country.factors)}>
                          <PolarGrid />
                          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 10 }} />
                          <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} />
                          <Radar
                            name={country.country}
                            dataKey="value"
                            stroke="#3B82F6"
                            fill="#3B82F6"
                            fillOpacity={0.6}
                          />
                        </RadarChart>
                      </ResponsiveContainer>
                    </div>

                    {/* 주요 지표 */}
                    <div className="grid grid-cols-3 gap-2 mt-4">
                      <div className="text-center p-2 bg-gray-50 rounded">
                        <div className="text-xs text-gray-600">GDP</div>
                        <div className="text-sm font-bold">{country.factors.gdp_score}</div>
                      </div>
                      <div className="text-center p-2 bg-gray-50 rounded">
                        <div className="text-xs text-gray-600">FTA</div>
                        <div className="text-sm font-bold">{country.factors.fta_score}</div>
                      </div>
                      <div className="text-center p-2 bg-gray-50 rounded">
                        <div className="text-xs text-gray-600">물류</div>
                        <div className="text-sm font-bold">{country.factors.lpi_score}</div>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* 비교 차트 */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-4">
                  국가별 예상 수출액 비교
                </h3>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={results.top_countries}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="country" />
                      <YAxis tickFormatter={(value) => formatCurrency(value)} />
                      <Tooltip
                        formatter={(value) => formatCurrency(value)}
                        labelStyle={{ color: '#000' }}
                      />
                      <Legend />
                      <Bar dataKey="predicted_export" fill="#3B82F6" name="예상 수출액" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* AI 분석 근거 */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <FileText className="w-6 h-6 text-blue-600" />
                  AI 분석 근거
                </h3>
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <h4 className="font-semibold text-gray-800 mb-3">주요 영향 요인</h4>
                    <ul className="space-y-2">
                      {results.explanation.primary_factors.map((factor, index) => (
                        <li key={index} className="flex items-center gap-2">
                          <div className="w-2 h-2 bg-blue-600 rounded-full"></div>
                          <span className="text-gray-700">{factor}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-800 mb-3">인사이트</h4>
                    <ul className="space-y-2">
                      {results.explanation.insights.map((insight, index) => (
                        <li key={index} className="flex items-start gap-2">
                          <TrendingUp className="w-4 h-4 text-green-600 mt-1 flex-shrink-0" />
                          <span className="text-gray-700">{insight}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>

              {/* 6개 요인 설명 */}
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h3 className="text-xl font-bold text-gray-900 mb-4">
                  분석 요인 설명
                </h3>
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {[
                    { icon: <DollarSign />, name: 'GDP', desc: '대상국의 경제 규모' },
                    { icon: <Globe />, name: '거리', desc: '한국과의 지리적 거리' },
                    { icon: <FileText />, name: 'FTA', desc: '자유무역협정 체결 여부' },
                    { icon: <Truck />, name: '물류', desc: '물류 성과 지수 (LPI)' },
                    { icon: <TrendingUp />, name: '관세', desc: '관세율 및 무역 장벽' },
                    { icon: <Users />, name: '문화', desc: '문화적 유사성 지수' }
                  ].map((factor, index) => (
                    <div key={index} className="p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <div className="text-blue-600">{factor.icon}</div>
                        <div className="font-semibold text-gray-800">{factor.name}</div>
                      </div>
                      <p className="text-sm text-gray-600">{factor.desc}</p>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default AnalysisPage;
