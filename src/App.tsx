import { useState, useEffect } from 'react'
import ExportHubMVP from './components/ExportHubMVP'
import AdminDashboard from './components/AdminDashboard'

function App() {
  const [isAdmin, setIsAdmin] = useState(false)

  useEffect(() => {
    // Check URL hash for admin route
    const checkRoute = () => {
      setIsAdmin(window.location.hash === '#/admin')
    }
    checkRoute()
    window.addEventListener('hashchange', checkRoute)
    return () => window.removeEventListener('hashchange', checkRoute)
  }, [])

  if (isAdmin) {
    return (
      <div>
        <AdminDashboard />
        <button
          onClick={() => window.location.hash = '/'}
          className="fixed bottom-4 right-4 px-4 py-2 bg-gray-800 text-white rounded-lg shadow-lg hover:bg-gray-700 transition flex items-center gap-2 z-50"
        >
          <span>🌍</span> Back to Main App
        </button>
      </div>
    )
  }

  return (
    <div>
      <ExportHubMVP />
      <button
        onClick={() => window.location.hash = '#/admin'}
        className="fixed bottom-4 right-4 px-4 py-2 bg-indigo-600 text-white rounded-lg shadow-lg hover:bg-indigo-700 transition flex items-center gap-2 z-50"
      >
        <span>⚙️</span> Admin Console
      </button>
    </div>
  )
}

export default App
