import React, { useState } from 'react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

// Types
interface User {
  id: string;
  name: string;
  email: string;
  company: string;
  plan: 'free' | 'pro' | 'enterprise';
  status: 'active' | 'inactive' | 'pending';
  joinedAt: string;
  lastLogin: string;
  exports: number;
}

interface CountryData {
  id: string;
  country: string;
  countryCode: string;
  flag: string;
  marketSize: number;
  growthRate: number;
  tariff: number;
  lastUpdated: string;
  status: 'active' | 'needs_update';
}

interface BuyerData {
  id: string;
  name: string;
  country: string;
  flag: string;
  verified: boolean;
  verificationDate?: string;
  contactCount: number;
  dealsClosed: number;
  status: 'pending' | 'verified' | 'rejected';
}

interface Analytics {
  dailyUsers: { date: string; users: number; newUsers: number }[];
  countrySearches: { country: string; searches: number }[];
  planDistribution: { name: string; value: number }[];
  monthlyRevenue: { month: string; revenue: number; target: number }[];
}

// Mock Data
const mockUsers: User[] = [
  { id: '1', name: '김수출', email: 'kim@abc.co.kr', company: 'ABC Company', plan: 'pro', status: 'active', joinedAt: '2025-11-15', lastLogin: '2026-01-22', exports: 12 },
  { id: '2', name: '이무역', email: 'lee@xyz.co.kr', company: 'XYZ Trading', plan: 'enterprise', status: 'active', joinedAt: '2025-10-20', lastLogin: '2026-01-21', exports: 45 },
  { id: '3', name: '박글로벌', email: 'park@global.kr', company: 'Global Corp', plan: 'free', status: 'active', joinedAt: '2026-01-10', lastLogin: '2026-01-20', exports: 3 },
  { id: '4', name: '최바이어', email: 'choi@buyer.kr', company: 'Buyer Korea', plan: 'pro', status: 'inactive', joinedAt: '2025-09-05', lastLogin: '2025-12-15', exports: 8 },
  { id: '5', name: '정수입', email: 'jung@import.kr', company: 'Import Co', plan: 'free', status: 'pending', joinedAt: '2026-01-20', lastLogin: '2026-01-20', exports: 0 },
];

const mockCountries: CountryData[] = [
  { id: '1', country: '베트남', countryCode: 'VN', flag: '🇻🇳', marketSize: 1200000000, growthRate: 12.5, tariff: 0, lastUpdated: '2026-01-15', status: 'active' },
  { id: '2', country: '태국', countryCode: 'TH', flag: '🇹🇭', marketSize: 980000000, growthRate: 9.8, tariff: 2.5, lastUpdated: '2026-01-14', status: 'active' },
  { id: '3', country: '인도네시아', countryCode: 'ID', flag: '🇮🇩', marketSize: 1500000000, growthRate: 11.2, tariff: 5, lastUpdated: '2025-12-20', status: 'needs_update' },
  { id: '4', country: '말레이시아', countryCode: 'MY', flag: '🇲🇾', marketSize: 650000000, growthRate: 8.5, tariff: 0, lastUpdated: '2026-01-10', status: 'active' },
  { id: '5', country: '필리핀', countryCode: 'PH', flag: '🇵🇭', marketSize: 720000000, growthRate: 10.3, tariff: 3, lastUpdated: '2025-12-28', status: 'needs_update' },
];

const mockBuyers: BuyerData[] = [
  { id: '1', name: 'Vietnam Cosmetics Co.', country: 'VN', flag: '🇻🇳', verified: true, verificationDate: '2025-12-01', contactCount: 45, dealsClosed: 12, status: 'verified' },
  { id: '2', name: 'Hanoi Beauty Import', country: 'VN', flag: '🇻🇳', verified: true, verificationDate: '2025-11-15', contactCount: 32, dealsClosed: 8, status: 'verified' },
  { id: '3', name: 'Bangkok Trading Ltd.', country: 'TH', flag: '🇹🇭', verified: false, contactCount: 18, dealsClosed: 0, status: 'pending' },
  { id: '4', name: 'Jakarta Beauty House', country: 'ID', flag: '🇮🇩', verified: true, verificationDate: '2026-01-05', contactCount: 25, dealsClosed: 5, status: 'verified' },
  { id: '5', name: 'Saigon Import Export', country: 'VN', flag: '🇻🇳', verified: false, contactCount: 8, dealsClosed: 0, status: 'rejected' },
];

const mockAnalytics: Analytics = {
  dailyUsers: [
    { date: '01/16', users: 120, newUsers: 8 },
    { date: '01/17', users: 135, newUsers: 12 },
    { date: '01/18', users: 142, newUsers: 7 },
    { date: '01/19', users: 128, newUsers: 5 },
    { date: '01/20', users: 156, newUsers: 15 },
    { date: '01/21', users: 168, newUsers: 18 },
    { date: '01/22', users: 175, newUsers: 10 },
  ],
  countrySearches: [
    { country: '베트남', searches: 342 },
    { country: '태국', searches: 256 },
    { country: '인도네시아', searches: 198 },
    { country: '말레이시아', searches: 145 },
    { country: '필리핀', searches: 132 },
  ],
  planDistribution: [
    { name: 'Free', value: 450 },
    { name: 'Pro', value: 280 },
    { name: 'Enterprise', value: 85 },
  ],
  monthlyRevenue: [
    { month: '2025-08', revenue: 12500, target: 15000 },
    { month: '2025-09', revenue: 18200, target: 18000 },
    { month: '2025-10', revenue: 22100, target: 20000 },
    { month: '2025-11', revenue: 25800, target: 25000 },
    { month: '2025-12', revenue: 28500, target: 28000 },
    { month: '2026-01', revenue: 24200, target: 30000 },
  ],
};

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'];

// Components
const AdminTabButton = ({ active, onClick, children, icon, badge }: { active: boolean; onClick: () => void; children: React.ReactNode; icon: string; badge?: number }) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-2 px-4 py-3 text-sm font-medium rounded-lg transition-all w-full text-left ${
      active ? 'bg-indigo-600 text-white shadow-lg' : 'text-gray-600 hover:bg-gray-100'
    }`}
  >
    <span>{icon}</span>
    <span className="flex-1">{children}</span>
    {badge !== undefined && badge > 0 && (
      <span className={`px-2 py-0.5 text-xs rounded-full ${active ? 'bg-white text-indigo-600' : 'bg-red-100 text-red-600'}`}>
        {badge}
      </span>
    )}
  </button>
);

const StatCard = ({ title, value, change, icon, color }: { title: string; value: string | number; change?: string; icon: string; color: string }) => (
  <div className="bg-white rounded-xl p-6 shadow-sm">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm text-gray-500">{title}</p>
        <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
        {change && (
          <p className={`text-sm mt-1 ${change.startsWith('+') ? 'text-green-600' : 'text-red-600'}`}>
            {change} vs last month
          </p>
        )}
      </div>
      <div className={`w-12 h-12 ${color} rounded-xl flex items-center justify-center text-2xl`}>
        {icon}
      </div>
    </div>
  </div>
);

const StatusBadge = ({ status }: { status: string }) => {
  const styles: Record<string, string> = {
    active: 'bg-green-100 text-green-700',
    inactive: 'bg-gray-100 text-gray-600',
    pending: 'bg-yellow-100 text-yellow-700',
    verified: 'bg-blue-100 text-blue-700',
    rejected: 'bg-red-100 text-red-700',
    needs_update: 'bg-orange-100 text-orange-700',
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-100 text-gray-600'}`}>
      {status === 'needs_update' ? 'Update Required' : status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
};

const PlanBadge = ({ plan }: { plan: string }) => {
  const styles: Record<string, string> = {
    free: 'bg-gray-100 text-gray-600',
    pro: 'bg-indigo-100 text-indigo-700',
    enterprise: 'bg-purple-100 text-purple-700',
  };
  return (
    <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[plan]}`}>
      {plan.charAt(0).toUpperCase() + plan.slice(1)}
    </span>
  );
};

// Main Admin Component
export default function AdminDashboard() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'users' | 'countries' | 'buyers' | 'analytics' | 'settings'>('dashboard');
  const [searchQuery, setSearchQuery] = useState('');
  const [userFilter, setUserFilter] = useState<'all' | 'active' | 'inactive' | 'pending'>('all');
  const [buyerFilter, setBuyerFilter] = useState<'all' | 'pending' | 'verified' | 'rejected'>('all');

  // Filter users
  const filteredUsers = mockUsers.filter(user => {
    const matchSearch = user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                       user.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
                       user.company.toLowerCase().includes(searchQuery.toLowerCase());
    const matchFilter = userFilter === 'all' || user.status === userFilter;
    return matchSearch && matchFilter;
  });

  // Filter buyers
  const filteredBuyers = mockBuyers.filter(buyer => {
    const matchSearch = buyer.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchFilter = buyerFilter === 'all' || buyer.status === buyerFilter;
    return matchSearch && matchFilter;
  });

  // Pending counts
  const pendingUsers = mockUsers.filter(u => u.status === 'pending').length;
  const pendingBuyers = mockBuyers.filter(b => b.status === 'pending').length;
  const needsUpdateCountries = mockCountries.filter(c => c.status === 'needs_update').length;

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r min-h-screen p-4 flex flex-col">
        <div className="flex items-center gap-3 mb-8 px-2">
          <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center text-white text-xl">🌍</div>
          <div>
            <h1 className="text-lg font-bold text-gray-900">ExportHub</h1>
            <p className="text-xs text-gray-500">Admin Console</p>
          </div>
        </div>

        <nav className="space-y-1 flex-1">
          <AdminTabButton active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} icon="📊">
            Dashboard
          </AdminTabButton>
          <AdminTabButton active={activeTab === 'users'} onClick={() => setActiveTab('users')} icon="👥" badge={pendingUsers}>
            Users
          </AdminTabButton>
          <AdminTabButton active={activeTab === 'countries'} onClick={() => setActiveTab('countries')} icon="🌍" badge={needsUpdateCountries}>
            Countries
          </AdminTabButton>
          <AdminTabButton active={activeTab === 'buyers'} onClick={() => setActiveTab('buyers')} icon="🏢" badge={pendingBuyers}>
            Buyers
          </AdminTabButton>
          <AdminTabButton active={activeTab === 'analytics'} onClick={() => setActiveTab('analytics')} icon="📈">
            Analytics
          </AdminTabButton>
          <AdminTabButton active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} icon="⚙️">
            Settings
          </AdminTabButton>
        </nav>

        <div className="border-t pt-4 mt-4">
          <div className="flex items-center gap-3 px-2">
            <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-sm">👤</div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">Admin User</p>
              <p className="text-xs text-gray-500 truncate">admin@exporthub.io</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-8">
        {/* Dashboard */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
              <p className="text-gray-500 mt-1">Welcome back! Here's what's happening today.</p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard title="Total Users" value="815" change="+12.5%" icon="👥" color="bg-blue-100" />
              <StatCard title="Active Countries" value="127" change="+3" icon="🌍" color="bg-green-100" />
              <StatCard title="Verified Buyers" value="1,234" change="+8.2%" icon="🏢" color="bg-purple-100" />
              <StatCard title="Monthly Revenue" value="$24.2K" change="-5.8%" icon="💰" color="bg-yellow-100" />
            </div>

            {/* Charts Row */}
            <div className="grid lg:grid-cols-2 gap-6">
              <div className="bg-white rounded-xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-4">Daily Active Users</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={mockAnalytics.dailyUsers}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="users" stroke="#3b82f6" strokeWidth={2} />
                    <Line type="monotone" dataKey="newUsers" stroke="#10b981" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-4">Top Searched Countries</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={mockAnalytics.countrySearches} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" />
                    <YAxis dataKey="country" type="category" width={80} />
                    <Tooltip />
                    <Bar dataKey="searches" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Recent Activity */}
            <div className="bg-white rounded-xl p-6 shadow-sm">
              <h3 className="font-semibold text-gray-900 mb-4">Recent Activity</h3>
              <div className="space-y-4">
                {[
                  { icon: '👤', text: 'New user registered: 정수입 (Import Co)', time: '2 hours ago', color: 'bg-blue-100' },
                  { icon: '✅', text: 'Buyer verified: Jakarta Beauty House', time: '4 hours ago', color: 'bg-green-100' },
                  { icon: '📊', text: 'Country data updated: Vietnam market size', time: '6 hours ago', color: 'bg-purple-100' },
                  { icon: '💬', text: 'New chat initiated: ABC Company ↔ Vietnam Cosmetics', time: '8 hours ago', color: 'bg-yellow-100' },
                  { icon: '📄', text: 'Contract generated: $50,000 deal', time: '12 hours ago', color: 'bg-indigo-100' },
                ].map((activity, i) => (
                  <div key={i} className="flex items-center gap-4">
                    <div className={`w-10 h-10 ${activity.color} rounded-full flex items-center justify-center`}>
                      {activity.icon}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm text-gray-900">{activity.text}</p>
                      <p className="text-xs text-gray-500">{activity.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Users Management */}
        {activeTab === 'users' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">User Management</h2>
                <p className="text-gray-500 mt-1">Manage platform users and their subscriptions</p>
              </div>
              <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition flex items-center gap-2">
                <span>➕</span> Add User
              </button>
            </div>

            {/* Filters */}
            <div className="bg-white rounded-xl p-4 shadow-sm">
              <div className="flex flex-wrap gap-4">
                <div className="flex-1 min-w-[200px]">
                  <input
                    type="text"
                    placeholder="Search users..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                  />
                </div>
                <div className="flex gap-2">
                  {(['all', 'active', 'inactive', 'pending'] as const).map(filter => (
                    <button
                      key={filter}
                      onClick={() => setUserFilter(filter)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                        userFilter === filter ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {filter.charAt(0).toUpperCase() + filter.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Users Table */}
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">User</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Company</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Plan</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Exports</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Login</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {filteredUsers.map(user => (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 bg-indigo-100 rounded-full flex items-center justify-center text-sm font-medium text-indigo-600">
                            {user.name.charAt(0)}
                          </div>
                          <div>
                            <p className="text-sm font-medium text-gray-900">{user.name}</p>
                            <p className="text-xs text-gray-500">{user.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-600">{user.company}</td>
                      <td className="px-6 py-4"><PlanBadge plan={user.plan} /></td>
                      <td className="px-6 py-4"><StatusBadge status={user.status} /></td>
                      <td className="px-6 py-4 text-sm text-gray-600">{user.exports}</td>
                      <td className="px-6 py-4 text-sm text-gray-500">{user.lastLogin}</td>
                      <td className="px-6 py-4 text-right">
                        <button className="text-indigo-600 hover:text-indigo-800 text-sm font-medium mr-3">Edit</button>
                        <button className="text-red-600 hover:text-red-800 text-sm font-medium">Delete</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Countries Management */}
        {activeTab === 'countries' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Country Data Management</h2>
                <p className="text-gray-500 mt-1">Manage market data and country information</p>
              </div>
              <div className="flex gap-2">
                <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition flex items-center gap-2">
                  <span>🔄</span> Sync KOTRA Data
                </button>
                <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition flex items-center gap-2">
                  <span>➕</span> Add Country
                </button>
              </div>
            </div>

            {/* Countries Grid */}
            <div className="grid gap-4">
              {mockCountries.map(country => (
                <div key={country.id} className="bg-white rounded-xl p-6 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="text-4xl">{country.flag}</div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-lg font-bold text-gray-900">{country.country}</span>
                          <span className="text-sm text-gray-500">({country.countryCode})</span>
                          <StatusBadge status={country.status} />
                        </div>
                        <div className="flex gap-6 mt-2 text-sm text-gray-500">
                          <span>Market Size: ${(country.marketSize / 1000000000).toFixed(1)}B</span>
                          <span>Growth: {country.growthRate}%</span>
                          <span>Tariff: {country.tariff}%</span>
                          <span>Updated: {country.lastUpdated}</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button className="px-4 py-2 bg-indigo-100 text-indigo-700 rounded-lg text-sm font-medium hover:bg-indigo-200 transition">
                        Edit
                      </button>
                      <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition">
                        View Details
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Buyers Management */}
        {activeTab === 'buyers' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Buyer Verification</h2>
                <p className="text-gray-500 mt-1">Verify and manage buyer profiles</p>
              </div>
              <button className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition flex items-center gap-2">
                <span>➕</span> Add Buyer
              </button>
            </div>

            {/* Filters */}
            <div className="bg-white rounded-xl p-4 shadow-sm">
              <div className="flex flex-wrap gap-4">
                <div className="flex-1 min-w-[200px]">
                  <input
                    type="text"
                    placeholder="Search buyers..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                  />
                </div>
                <div className="flex gap-2">
                  {(['all', 'pending', 'verified', 'rejected'] as const).map(filter => (
                    <button
                      key={filter}
                      onClick={() => setBuyerFilter(filter)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                        buyerFilter === filter ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {filter.charAt(0).toUpperCase() + filter.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Buyers Grid */}
            <div className="grid gap-4">
              {filteredBuyers.map(buyer => (
                <div key={buyer.id} className="bg-white rounded-xl p-6 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center text-2xl">
                        {buyer.flag}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-gray-900">{buyer.name}</span>
                          <StatusBadge status={buyer.status} />
                        </div>
                        <div className="flex gap-4 mt-1 text-sm text-gray-500">
                          <span>Contacts: {buyer.contactCount}</span>
                          <span>Deals Closed: {buyer.dealsClosed}</span>
                          {buyer.verificationDate && <span>Verified: {buyer.verificationDate}</span>}
                        </div>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      {buyer.status === 'pending' && (
                        <>
                          <button className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition">
                            ✓ Verify
                          </button>
                          <button className="px-4 py-2 bg-red-100 text-red-700 rounded-lg text-sm font-medium hover:bg-red-200 transition">
                            ✗ Reject
                          </button>
                        </>
                      )}
                      <button className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition">
                        View Profile
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Analytics */}
        {activeTab === 'analytics' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Analytics</h2>
              <p className="text-gray-500 mt-1">Platform performance and insights</p>
            </div>

            {/* Revenue Chart */}
            <div className="bg-white rounded-xl p-6 shadow-sm">
              <h3 className="font-semibold text-gray-900 mb-4">Monthly Revenue vs Target</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={mockAnalytics.monthlyRevenue}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip formatter={(value) => `$${value}`} />
                  <Legend />
                  <Bar dataKey="revenue" fill="#3b82f6" name="Revenue" />
                  <Bar dataKey="target" fill="#e5e7eb" name="Target" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
              {/* Plan Distribution */}
              <div className="bg-white rounded-xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-4">User Plan Distribution</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={mockAnalytics.planDistribution}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={5}
                      dataKey="value"
                      label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                    >
                      {mockAnalytics.planDistribution.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>

              {/* Key Metrics */}
              <div className="bg-white rounded-xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-4">Key Metrics</h3>
                <div className="space-y-4">
                  {[
                    { label: 'Avg. Session Duration', value: '12m 34s', change: '+8%' },
                    { label: 'Buyer Match Rate', value: '78.5%', change: '+2.3%' },
                    { label: 'Contract Conversion', value: '23.4%', change: '+5.1%' },
                    { label: 'User Retention (30d)', value: '85.2%', change: '-1.2%' },
                    { label: 'NPS Score', value: '72', change: '+4' },
                  ].map((metric, i) => (
                    <div key={i} className="flex items-center justify-between py-2 border-b last:border-0">
                      <span className="text-sm text-gray-600">{metric.label}</span>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-gray-900">{metric.value}</span>
                        <span className={`text-xs ${metric.change.startsWith('+') ? 'text-green-600' : 'text-red-600'}`}>
                          {metric.change}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Settings */}
        {activeTab === 'settings' && (
          <div className="space-y-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Settings</h2>
              <p className="text-gray-500 mt-1">Platform configuration and preferences</p>
            </div>

            <div className="grid gap-6">
              {/* General Settings */}
              <div className="bg-white rounded-xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-4">General Settings</h3>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Platform Name</label>
                      <input
                        type="text"
                        defaultValue="ExportHub"
                        className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Support Email</label>
                      <input
                        type="email"
                        defaultValue="support@exporthub.io"
                        className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* API Settings */}
              <div className="bg-white rounded-xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-4">API Integrations</h3>
                <div className="space-y-4">
                  {[
                    { name: 'KOTRA Open API', status: 'connected', key: 'kotra_***************' },
                    { name: 'Translation API', status: 'connected', key: 'trans_***************' },
                    { name: 'Payment Gateway', status: 'pending', key: '' },
                  ].map((api, i) => (
                    <div key={i} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div>
                        <p className="font-medium text-gray-900">{api.name}</p>
                        <p className="text-sm text-gray-500">{api.key || 'Not configured'}</p>
                      </div>
                      <StatusBadge status={api.status === 'connected' ? 'active' : 'pending'} />
                    </div>
                  ))}
                </div>
              </div>

              {/* Notification Settings */}
              <div className="bg-white rounded-xl p-6 shadow-sm">
                <h3 className="font-semibold text-gray-900 mb-4">Notifications</h3>
                <div className="space-y-4">
                  {[
                    { label: 'Email notifications for new users', enabled: true },
                    { label: 'Slack alerts for buyer verification', enabled: true },
                    { label: 'Weekly analytics report', enabled: false },
                    { label: 'System maintenance alerts', enabled: true },
                  ].map((setting, i) => (
                    <div key={i} className="flex items-center justify-between py-2">
                      <span className="text-sm text-gray-700">{setting.label}</span>
                      <button
                        className={`w-12 h-6 rounded-full transition ${setting.enabled ? 'bg-indigo-600' : 'bg-gray-200'}`}
                      >
                        <div className={`w-5 h-5 bg-white rounded-full shadow transition transform ${setting.enabled ? 'translate-x-6' : 'translate-x-0.5'}`} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
