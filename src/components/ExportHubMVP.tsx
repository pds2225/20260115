import React, { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

// Types
interface Country {
  country: string;
  countryCode: string;
  flag: string;
  score: number;
  marketSize: number;
  growthRate: number;
  tariff: number;
  reasoning: string;
  risks: string[];
  opportunities: string[];
}

interface Buyer {
  id: string;
  name: string;
  country: string;
  flag: string;
  products: string[];
  dealSize: string;
  verified: boolean;
  fitScore: number;
  matchReasons: string[];
  email: string;
}

interface Message {
  id: string;
  senderId: string;
  senderName: string;
  content: string;
  translated?: string;
  language: string;
  createdAt: string;
  isMine: boolean;
}

// Mock Data
const mockRecommendations: Country[] = [
  { country: '베트남', countryCode: 'VN', flag: '🇻🇳', score: 85, marketSize: 1200000000, growthRate: 12.5, tariff: 0, reasoning: '높은 성장률, FTA 혜택, K-뷰티 선호', risks: ['물류비 상승', '현지 경쟁 심화'], opportunities: ['온라인 시장 급성장', '젊은 소비층 확대'] },
  { country: '태국', countryCode: 'TH', flag: '🇹🇭', score: 82, marketSize: 980000000, growthRate: 9.8, tariff: 2.5, reasoning: '안정적 시장, 유통망 발달', risks: ['환율 변동성'], opportunities: ['프리미엄 시장 성장'] },
  { country: '인도네시아', countryCode: 'ID', flag: '🇮🇩', score: 78, marketSize: 1500000000, growthRate: 11.2, tariff: 5, reasoning: '대규모 인구, 중산층 확대', risks: ['복잡한 규제', '물류 인프라'], opportunities: ['디지털 커머스 성장'] },
  { country: '말레이시아', countryCode: 'MY', flag: '🇲🇾', score: 75, marketSize: 650000000, growthRate: 8.5, tariff: 0, reasoning: 'FTA 체결, 높은 구매력', risks: ['내수 시장 한계'], opportunities: ['할랄 시장 진출 거점'] },
  { country: '필리핀', countryCode: 'PH', flag: '🇵🇭', score: 72, marketSize: 720000000, growthRate: 10.3, tariff: 3, reasoning: '젊은 인구 구조, 영어 사용', risks: ['인프라 부족'], opportunities: ['SNS 마케팅 효과적'] },
];

const mockBuyers: Buyer[] = [
  { id: '1', name: 'Vietnam Cosmetics Co.', country: 'VN', flag: '🇻🇳', products: ['스킨케어', '메이크업'], dealSize: '$50K-$200K', verified: true, fitScore: 92, matchReasons: ['품목 100% 일치', '거래 규모 적합', 'KOTRA 검증'], email: 'contact@vncosmetics.com' },
  { id: '2', name: 'Hanoi Beauty Import', country: 'VN', flag: '🇻🇳', products: ['스킨케어', '헤어케어'], dealSize: '$30K-$100K', verified: true, fitScore: 85, matchReasons: ['품목 80% 일치', '신규 거래처 확장 중'], email: 'buy@hanoibeauty.vn' },
  { id: '3', name: 'Bangkok Trading Ltd.', country: 'TH', flag: '🇹🇭', products: ['메이크업', '향수'], dealSize: '$100K-$500K', verified: false, fitScore: 78, matchReasons: ['품목 60% 일치', '대형 거래 가능'], email: 'info@bangkoktrading.th' },
  { id: '4', name: 'Jakarta Beauty House', country: 'ID', flag: '🇮🇩', products: ['스킨케어'], dealSize: '$20K-$80K', verified: true, fitScore: 75, matchReasons: ['품목 일치', '성장 잠재력'], email: 'purchase@jktbeauty.id' },
];

const mockMessages: Message[] = [
  { id: '1', senderId: 'me', senderName: 'ABC Company', content: '안녕하세요, 샘플 발송 가능한가요?', translated: 'Hello, is sample shipment available?', language: 'ko', createdAt: '11:30', isMine: true },
  { id: '2', senderId: 'buyer', senderName: 'Vietnam Cosmetics', content: 'Yes, please send samples to our Hanoi office.', translated: '네, 하노이 사무실로 샘플을 보내주세요.', language: 'en', createdAt: '11:32', isMine: false },
  { id: '3', senderId: 'me', senderName: 'ABC Company', content: '배송비는 어떻게 처리할까요?', translated: 'How should we handle shipping costs?', language: 'ko', createdAt: '11:35', isMine: true },
];

// Components
const TabButton = ({ active, onClick, children, icon }: { active: boolean; onClick: () => void; children: React.ReactNode; icon: string }) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-2 px-4 py-3 text-sm font-medium rounded-lg transition-all ${
      active ? 'bg-blue-600 text-white shadow-lg' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
    }`}
  >
    <span>{icon}</span>
    <span className="hidden sm:inline">{children}</span>
  </button>
);

const ScoreBadge = ({ score }: { score: number }) => {
  const color = score >= 80 ? 'bg-green-100 text-green-700' : score >= 70 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-700';
  return <span className={`px-3 py-1 rounded-full text-sm font-bold ${color}`}>{score}/100</span>;
};

const VerifiedBadge = () => (
  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">
    <span>🛡️</span> KOTRA 검증
  </span>
);

// Main App
export default function ExportHubMVP() {
  const [activeTab, setActiveTab] = useState<'recommend' | 'simulator' | 'buyers' | 'chat' | 'contract'>('recommend');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCountry, setSelectedCountry] = useState<Country | null>(null);

  // Simulator State
  const [targetShare, setTargetShare] = useState(0.5);
  const [productPrice, setProductPrice] = useState(50);
  const [marketingBudget, setMarketingBudget] = useState(20000);

  // Buyer Search State
  const [buyerSearch, setBuyerSearch] = useState('');
  const [buyerCountry, setBuyerCountry] = useState('all');
  const [verifiedOnly, setVerifiedOnly] = useState(false);

  // Chat State
  const [messages, setMessages] = useState<Message[]>(mockMessages);
  const [newMessage, setNewMessage] = useState('');
  const [autoTranslate, setAutoTranslate] = useState(true);

  // Contract State
  const [contract, setContract] = useState({
    buyerName: 'Vietnam Cosmetics Co.',
    buyerAddress: '123 Hanoi Street, Vietnam',
    product: 'Organic Skincare Set',
    quantity: 1000,
    unitPrice: 50,
    incoterms: 'FOB',
    paymentTerms: '30 days',
    deliveryDate: '2026-03-01'
  });

  // Simulate loading
  const simulateLoading = () => {
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
    }, 2000);
  };

  // Simulator calculations
  const marketSize = selectedCountry?.marketSize || 1200000000;
  const baseRevenue = marketSize * (targetShare / 100);
  const simulatorData = [
    { name: '1차년도', 보수적: Math.round(baseRevenue * 0.2 * 0.3 / 1000), 현실적: Math.round(baseRevenue * 0.2 * 0.5 / 1000), 낙관적: Math.round(baseRevenue * 0.2 * 0.8 / 1000) },
    { name: '2차년도', 보수적: Math.round(baseRevenue * 0.5 * 0.3 / 1000), 현실적: Math.round(baseRevenue * 0.5 * 0.5 / 1000), 낙관적: Math.round(baseRevenue * 0.5 * 0.8 / 1000) },
    { name: '3차년도', 보수적: Math.round(baseRevenue * 1.0 * 0.3 / 1000), 현실적: Math.round(baseRevenue * 1.0 * 0.5 / 1000), 낙관적: Math.round(baseRevenue * 1.0 * 0.8 / 1000) },
  ];

  // Filter buyers
  const filteredBuyers = mockBuyers.filter(buyer => {
    const matchSearch = buyer.name.toLowerCase().includes(buyerSearch.toLowerCase()) ||
                       buyer.products.some(p => p.includes(buyerSearch));
    const matchCountry = buyerCountry === 'all' || buyer.country === buyerCountry;
    const matchVerified = !verifiedOnly || buyer.verified;
    return matchSearch && matchCountry && matchVerified;
  });

  // Send message
  const sendMessage = () => {
    if (!newMessage.trim()) return;
    const msg: Message = {
      id: Date.now().toString(),
      senderId: 'me',
      senderName: 'ABC Company',
      content: newMessage,
      translated: 'Translation in progress...',
      language: 'ko',
      createdAt: new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }),
      isMine: true
    };
    setMessages([...messages, msg]);
    setNewMessage('');

    // Simulate translation
    setTimeout(() => {
      setMessages(prev => prev.map(m =>
        m.id === msg.id ? { ...m, translated: `[Translated] ${newMessage}` } : m
      ));
    }, 1500);
  };

  // Generate PDF (simulated)
  const generatePDF = () => {
    alert('📄 계약서 PDF가 생성되었습니다!\n\n실제 구현에서는 jsPDF를 사용하여 다운로드됩니다.');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center text-white text-xl">🌍</div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">ExportHub</h1>
                <p className="text-xs text-gray-500">글로벌 수출 인텔리전스 플랫폼</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">ABC Company</span>
              <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center">👤</div>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex gap-2 overflow-x-auto">
            <TabButton active={activeTab === 'recommend'} onClick={() => setActiveTab('recommend')} icon="🎯">유망국가 추천</TabButton>
            <TabButton active={activeTab === 'simulator'} onClick={() => setActiveTab('simulator')} icon="📊">매출 시뮬레이터</TabButton>
            <TabButton active={activeTab === 'buyers'} onClick={() => setActiveTab('buyers')} icon="🔍">바이어 매칭</TabButton>
            <TabButton active={activeTab === 'chat'} onClick={() => setActiveTab('chat')} icon="💬">번역 채팅</TabButton>
            <TabButton active={activeTab === 'contract'} onClick={() => setActiveTab('contract')} icon="📄">계약서 생성</TabButton>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">

        {/* 유망국가 추천 */}
        {activeTab === 'recommend' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">🌍 맞춤 유망국가 추천</h2>
                <p className="text-gray-500 mt-1">귀사의 제품과 수출 경험을 기반으로 최적의 진출 국가를 추천합니다</p>
              </div>
              <button
                onClick={() => simulateLoading()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2"
              >
                <span>🔄</span> 재분석
              </button>
            </div>

            {isLoading ? (
              <div className="bg-white rounded-2xl p-12 text-center shadow-sm">
                <div className="inline-block animate-spin text-4xl mb-4">🤖</div>
                <p className="text-lg font-medium text-gray-700">AI 분석 중...</p>
                <p className="text-sm text-gray-500 mt-2">127개국 데이터를 분석하고 있습니다</p>
                <div className="mt-4 w-64 mx-auto bg-gray-200 rounded-full h-2">
                  <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: '60%' }}></div>
                </div>
              </div>
            ) : (
              <div className="grid gap-4">
                {mockRecommendations.map((country, index) => (
                  <div
                    key={country.countryCode}
                    className={`bg-white rounded-2xl p-6 shadow-sm border-2 transition-all cursor-pointer ${
                      selectedCountry?.countryCode === country.countryCode ? 'border-blue-500' : 'border-transparent hover:border-blue-200'
                    }`}
                    onClick={() => setSelectedCountry(country)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-4">
                        <div className="text-4xl">{country.flag}</div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-lg font-bold text-gray-900">{index + 1}. {country.country}</span>
                            <ScoreBadge score={country.score} />
                          </div>
                          <div className="flex gap-4 mt-2 text-sm text-gray-500">
                            <span>시장 규모: ${(country.marketSize / 1000000000).toFixed(1)}B</span>
                            <span>성장률: {country.growthRate}%</span>
                            <span>관세: {country.tariff}%</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="mt-4 p-4 bg-gray-50 rounded-xl">
                      <p className="text-sm text-gray-700 mb-3">💡 {country.reasoning}</p>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-xs font-medium text-green-600 mb-1">✅ 기회 요인</p>
                          {country.opportunities.map((opp, i) => (
                            <p key={i} className="text-xs text-gray-600">• {opp}</p>
                          ))}
                        </div>
                        <div>
                          <p className="text-xs font-medium text-orange-600 mb-1">⚠️ 리스크</p>
                          {country.risks.map((risk, i) => (
                            <p key={i} className="text-xs text-gray-600">• {risk}</p>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-2 mt-4">
                      <button
                        onClick={(e) => { e.stopPropagation(); setSelectedCountry(country); setActiveTab('simulator'); }}
                        className="px-4 py-2 bg-blue-100 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-200 transition"
                      >
                        📊 시뮬레이터 실행
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); setBuyerCountry(country.countryCode); setActiveTab('buyers'); }}
                        className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition"
                      >
                        🔍 바이어 찾기
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 매출 시뮬레이터 */}
        {activeTab === 'simulator' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">📊 {selectedCountry?.country || '베트남'} 시장 진입 시뮬레이터</h2>
              <p className="text-gray-500 mt-1">슬라이더를 조절하여 예상 매출을 시뮬레이션하세요</p>
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
              {/* Controls */}
              <div className="bg-white rounded-2xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-4">시뮬레이션 변수</h3>

                <div className="space-y-6">
                  <div className="p-4 bg-blue-50 rounded-xl">
                    <p className="text-sm text-gray-600">시장 규모 (KOTRA 2025)</p>
                    <p className="text-2xl font-bold text-blue-600">${(marketSize / 1000000000).toFixed(1)}B</p>
                  </div>

                  <div>
                    <div className="flex justify-between mb-2">
                      <label className="text-sm font-medium text-gray-700">목표 점유율</label>
                      <span className="text-sm font-bold text-blue-600">{targetShare}%</span>
                    </div>
                    <input
                      type="range"
                      min="0.1"
                      max="5"
                      step="0.1"
                      value={targetShare}
                      onChange={(e) => setTargetShare(parseFloat(e.target.value))}
                      className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between mb-2">
                      <label className="text-sm font-medium text-gray-700">제품 단가</label>
                      <span className="text-sm font-bold text-blue-600">${productPrice}</span>
                    </div>
                    <input
                      type="range"
                      min="10"
                      max="500"
                      step="10"
                      value={productPrice}
                      onChange={(e) => setProductPrice(parseInt(e.target.value))}
                      className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between mb-2">
                      <label className="text-sm font-medium text-gray-700">마케팅 예산</label>
                      <span className="text-sm font-bold text-blue-600">${(marketingBudget / 1000).toFixed(0)}K</span>
                    </div>
                    <input
                      type="range"
                      min="5000"
                      max="100000"
                      step="5000"
                      value={marketingBudget}
                      onChange={(e) => setMarketingBudget(parseInt(e.target.value))}
                      className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                    />
                  </div>
                </div>
              </div>

              {/* Chart */}
              <div className="bg-white rounded-2xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-4">📈 예상 매출 (단위: $K)</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={simulatorData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip formatter={(value) => `$${value}K`} />
                    <Legend />
                    <Bar dataKey="보수적" fill="#94a3b8" />
                    <Bar dataKey="현실적" fill="#3b82f6" />
                    <Bar dataKey="낙관적" fill="#10b981" />
                  </BarChart>
                </ResponsiveContainer>

                <div className="grid grid-cols-3 gap-4 mt-6">
                  <div className="text-center p-3 bg-gray-100 rounded-xl">
                    <p className="text-xs text-gray-500">보수적</p>
                    <p className="text-lg font-bold text-gray-700">${simulatorData[0].보수적}K</p>
                  </div>
                  <div className="text-center p-3 bg-blue-100 rounded-xl">
                    <p className="text-xs text-blue-600">현실적</p>
                    <p className="text-lg font-bold text-blue-700">${simulatorData[0].현실적}K</p>
                  </div>
                  <div className="text-center p-3 bg-green-100 rounded-xl">
                    <p className="text-xs text-green-600">낙관적</p>
                    <p className="text-lg font-bold text-green-700">${simulatorData[0].낙관적}K</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Case Study */}
            <div className="bg-gradient-to-r from-blue-500 to-blue-600 rounded-2xl p-6 text-white">
              <div className="flex items-start gap-4">
                <span className="text-3xl">💡</span>
                <div>
                  <h4 className="font-semibold mb-1">유사 사례: A사(화장품) 베트남 진입</h4>
                  <p className="text-blue-100 text-sm">1차년도 $55K → 3차년도 $220K (400% 성장)</p>
                  <p className="text-blue-100 text-sm mt-1">성공 요인: 현지 인플루언서 마케팅, 온라인 채널 집중</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 바이어 매칭 */}
        {activeTab === 'buyers' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">🔍 바이어 매칭</h2>
              <p className="text-gray-500 mt-1">FitScore 기반으로 최적의 바이어를 찾아보세요</p>
            </div>

            {/* Search Filters */}
            <div className="bg-white rounded-2xl p-4 shadow-sm">
              <div className="flex flex-wrap gap-4">
                <div className="flex-1 min-w-[200px]">
                  <input
                    type="text"
                    placeholder="품목 또는 바이어명 검색..."
                    value={buyerSearch}
                    onChange={(e) => setBuyerSearch(e.target.value)}
                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  />
                </div>
                <select
                  value={buyerCountry}
                  onChange={(e) => setBuyerCountry(e.target.value)}
                  className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value="all">모든 국가</option>
                  <option value="VN">🇻🇳 베트남</option>
                  <option value="TH">🇹🇭 태국</option>
                  <option value="ID">🇮🇩 인도네시아</option>
                </select>
                <label className="flex items-center gap-2 px-4 py-2 bg-gray-100 rounded-lg cursor-pointer">
                  <input
                    type="checkbox"
                    checked={verifiedOnly}
                    onChange={(e) => setVerifiedOnly(e.target.checked)}
                    className="w-4 h-4 text-blue-600"
                  />
                  <span className="text-sm">검증 바이어만</span>
                </label>
              </div>
            </div>

            {/* Results */}
            <div className="text-sm text-gray-500">
              ✨ <strong>{filteredBuyers.length * 25 + 27}</strong>개 바이어 발견 (상위 {filteredBuyers.length}개 표시)
            </div>

            <div className="grid gap-4">
              {filteredBuyers.map((buyer) => (
                <div key={buyer.id} className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-md transition">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center text-2xl">
                        {buyer.flag}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-gray-900">{buyer.name}</span>
                          {buyer.verified && <VerifiedBadge />}
                        </div>
                        <div className="flex flex-wrap gap-2 mt-2">
                          {buyer.products.map((product, i) => (
                            <span key={i} className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
                              📦 {product}
                            </span>
                          ))}
                        </div>
                        <p className="text-sm text-gray-500 mt-2">💰 거래 규모: {buyer.dealSize}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="flex items-center gap-1">
                        <span className="text-yellow-500">⭐</span>
                        <span className="text-2xl font-bold text-gray-900">{buyer.fitScore}</span>
                      </div>
                      <p className="text-xs text-gray-500">FitScore</p>
                    </div>
                  </div>

                  <div className="mt-4 p-3 bg-green-50 rounded-xl">
                    <p className="text-xs font-medium text-green-700 mb-1">매칭 이유</p>
                    <div className="flex flex-wrap gap-2">
                      {buyer.matchReasons.map((reason, i) => (
                        <span key={i} className="text-xs text-green-600">• {reason}</span>
                      ))}
                    </div>
                  </div>

                  <div className="flex gap-2 mt-4">
                    <button className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition">
                      💬 채팅 시작
                    </button>
                    <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition">
                      프로필 보기
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 번역 채팅 */}
        {activeTab === 'chat' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">💬 Vietnam Cosmetics Co.와 대화</h2>
                <p className="text-gray-500 mt-1">실시간 자동 번역으로 언어 장벽 없이 소통하세요</p>
              </div>
              <label className="flex items-center gap-2 px-4 py-2 bg-white rounded-lg shadow-sm cursor-pointer">
                <span className="text-sm">🌐 자동번역</span>
                <input
                  type="checkbox"
                  checked={autoTranslate}
                  onChange={(e) => setAutoTranslate(e.target.checked)}
                  className="w-4 h-4 text-blue-600"
                />
              </label>
            </div>

            {/* Chat Messages */}
            <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
              <div className="h-[400px] overflow-y-auto p-4 space-y-4">
                {messages.map((msg) => (
                  <div key={msg.id} className={`flex ${msg.isMine ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[70%] ${msg.isMine ? 'order-2' : ''}`}>
                      <div className={`rounded-2xl p-4 ${msg.isMine ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-900'}`}>
                        <p className="text-sm">{msg.content}</p>
                        {autoTranslate && msg.translated && (
                          <p className={`text-xs mt-2 pt-2 border-t ${msg.isMine ? 'border-blue-500 text-blue-200' : 'border-gray-200 text-gray-500'}`}>
                            🌐 {msg.translated}
                          </p>
                        )}
                      </div>
                      <p className={`text-xs text-gray-400 mt-1 ${msg.isMine ? 'text-right' : ''}`}>
                        {msg.senderName} • {msg.createdAt}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Message Input */}
              <div className="border-t p-4">
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="메시지를 입력하세요..."
                    value={newMessage}
                    onChange={(e) => setNewMessage(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                    className="flex-1 px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <button className="px-4 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition">
                    📎
                  </button>
                  <button
                    onClick={sendMessage}
                    className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                  >
                    전송
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 계약서 생성 */}
        {activeTab === 'contract' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">📄 계약서 생성</h2>
              <p className="text-gray-500 mt-1">템플릿 기반으로 간편하게 계약서를 작성하세요</p>
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
              {/* Form */}
              <div className="bg-white rounded-2xl p-6 shadow-sm space-y-4">
                <h3 className="font-semibold text-gray-900">거래 정보 입력</h3>

                <div className="grid grid-cols-2 gap-4">
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">구매자</label>
                    <input
                      type="text"
                      value={contract.buyerName}
                      onChange={(e) => setContract({ ...contract, buyerName: e.target.value })}
                      className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">구매자 주소</label>
                    <input
                      type="text"
                      value={contract.buyerAddress}
                      onChange={(e) => setContract({ ...contract, buyerAddress: e.target.value })}
                      className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                  <div className="col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">제품명</label>
                    <input
                      type="text"
                      value={contract.product}
                      onChange={(e) => setContract({ ...contract, product: e.target.value })}
                      className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">수량</label>
                    <input
                      type="number"
                      value={contract.quantity}
                      onChange={(e) => setContract({ ...contract, quantity: parseInt(e.target.value) })}
                      className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">단가 ($)</label>
                    <input
                      type="number"
                      value={contract.unitPrice}
                      onChange={(e) => setContract({ ...contract, unitPrice: parseInt(e.target.value) })}
                      className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Incoterms</label>
                    <select
                      value={contract.incoterms}
                      onChange={(e) => setContract({ ...contract, incoterms: e.target.value })}
                      className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    >
                      <option value="FOB">FOB</option>
                      <option value="CIF">CIF</option>
                      <option value="EXW">EXW</option>
                      <option value="DDP">DDP</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">결제 조건</label>
                    <select
                      value={contract.paymentTerms}
                      onChange={(e) => setContract({ ...contract, paymentTerms: e.target.value })}
                      className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    >
                      <option value="30 days">30 days from B/L</option>
                      <option value="60 days">60 days from B/L</option>
                      <option value="L/C">L/C at Sight</option>
                      <option value="T/T">T/T in Advance</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">납품일</label>
                    <input
                      type="date"
                      value={contract.deliveryDate}
                      onChange={(e) => setContract({ ...contract, deliveryDate: e.target.value })}
                      className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                </div>

                <div className="pt-4 border-t">
                  <div className="flex justify-between text-lg font-bold">
                    <span>총 금액</span>
                    <span className="text-blue-600">${(contract.quantity * contract.unitPrice).toLocaleString()}</span>
                  </div>
                </div>
              </div>

              {/* Preview */}
              <div className="bg-white rounded-2xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-4">미리보기</h3>
                <div className="border rounded-xl p-6 bg-gray-50 font-mono text-sm space-y-4">
                  <div className="text-center border-b pb-4">
                    <h4 className="text-lg font-bold">SALES AGREEMENT</h4>
                    <p className="text-xs text-gray-500">Contract No: EH-2026-0122</p>
                  </div>

                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <p className="font-bold">SELLER:</p>
                      <p>ABC Company</p>
                      <p>Seoul, Korea</p>
                    </div>
                    <div>
                      <p className="font-bold">BUYER:</p>
                      <p>{contract.buyerName}</p>
                      <p>{contract.buyerAddress}</p>
                    </div>
                  </div>

                  <div className="border-t pt-4 text-xs">
                    <p><strong>Product:</strong> {contract.product}</p>
                    <p><strong>Quantity:</strong> {contract.quantity.toLocaleString()} units</p>
                    <p><strong>Unit Price:</strong> ${contract.unitPrice}</p>
                    <p><strong>Total Amount:</strong> ${(contract.quantity * contract.unitPrice).toLocaleString()}</p>
                  </div>

                  <div className="border-t pt-4 text-xs">
                    <p><strong>Incoterms:</strong> {contract.incoterms} Busan</p>
                    <p><strong>Payment:</strong> {contract.paymentTerms}</p>
                    <p><strong>Delivery:</strong> {contract.deliveryDate}</p>
                  </div>

                  <div className="border-t pt-4 grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <p className="mb-8">Seller Signature:</p>
                      <p className="border-t border-black">________________</p>
                    </div>
                    <div>
                      <p className="mb-8">Buyer Signature:</p>
                      <p className="border-t border-black">________________</p>
                    </div>
                  </div>
                </div>

                <div className="flex gap-2 mt-4">
                  <button
                    onClick={generatePDF}
                    className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition flex items-center justify-center gap-2"
                  >
                    📥 PDF 다운로드
                  </button>
                  <button className="px-4 py-3 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition">
                    ✉️ 이메일 발송
                  </button>
                </div>

                <div className="mt-4 p-3 bg-yellow-50 rounded-xl text-center">
                  <p className="text-sm text-yellow-700">💡 전자서명 기능 준비 중</p>
                  <button className="text-xs text-yellow-600 underline mt-1">베타 신청하기 →</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t mt-12">
        <div className="max-w-7xl mx-auto px-4 py-6 text-center text-sm text-gray-500">
          <p>© 2026 ExportHub. 글로벌 수출 인텔리전스 플랫폼</p>
          <p className="mt-1">MVP v1.0 | Powered by KOTRA Open API</p>
        </div>
      </footer>
    </div>
  );
}
