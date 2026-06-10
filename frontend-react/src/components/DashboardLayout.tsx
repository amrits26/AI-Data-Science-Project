import { useState, type KeyboardEvent } from 'react'
import { Outlet, Link, useLocation } from 'react-router-dom'
import { Menu, X, Car, DollarSign, FileText, MessageCircle } from 'lucide-react'

export default function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  const navItems = [
    { path: '/', label: 'Chat', icon: MessageCircle },
    { path: '/cars', label: 'Car Database', icon: Car },
    { path: '/financing', label: 'Financing Tools', icon: DollarSign },
    { path: '/paperwork', label: 'Paperwork', icon: FileText },
  ]

  const isActive = (path: string) => location.pathname === path

  // Close sidebar on Escape key
  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape' && sidebarOpen) setSidebarOpen(false)
  }

  return (
    <div className="flex h-screen bg-imperial-bg-light dark:bg-imperial-bg-dark" onKeyDown={handleKeyDown}>
      {/* Sidebar */}
      <div
        id="sidebar-nav"
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-imperial-surface dark:bg-imperial-surface-dark shadow-lg transform transition-transform duration-200 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } lg:relative lg:translate-x-0`}
      >
        <div className="p-6">
          <h1 className="text-2xl font-bold text-imperial-primary dark:text-imperial-primary-light">Imperial Cars</h1>
          <p className="text-sm text-imperial-text-secondary dark:text-imperial-text-secondary-dark">AI-Powered Dealership</p>
        </div>

        <nav className="mt-8" aria-label="Main navigation">
          {navItems.map(({ path, label, icon: Icon }) => (
            <Link
              key={path}
              to={path}
              onClick={() => setSidebarOpen(false)}
              className={`flex items-center px-6 py-3 transition-colors rounded-lg focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2 ${
                isActive(path)
                  ? 'bg-imperial-primary text-white border-r-4 border-imperial-gold'
                  : 'text-imperial-text dark:text-imperial-text-dark hover:bg-imperial-bg-light dark:hover:bg-imperial-bg-dark'
              }`}
            >
              <Icon className="w-5 h-5 mr-3" />
              <span className="font-medium">{label}</span>
            </Link>
          ))}
        </nav>

        <div className="absolute bottom-0 left-0 right-0 p-6 border-t border-imperial-border dark:border-imperial-border-dark bg-imperial-bg-light dark:bg-imperial-bg-dark">
          <p className="text-xs text-imperial-text-secondary dark:text-imperial-text-secondary-dark text-center">
            Version 1.0.0 | Powered by DeepSeek AI
          </p>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-imperial-surface dark:bg-imperial-surface-dark shadow-sm border-b border-imperial-border dark:border-imperial-border-dark">
          <div className="px-6 py-4 flex items-center justify-between">
            <button
              aria-label={sidebarOpen ? 'Close navigation menu' : 'Open navigation menu'}
              aria-controls="sidebar-nav"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="lg:hidden p-2 hover:bg-imperial-bg-light dark:hover:bg-imperial-bg-dark rounded-lg focus:outline-none focus:ring-2 focus:ring-imperial-primary focus:ring-offset-2"
            >
              {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>

            <div className="flex-1" />

            <div className="flex items-center space-x-4">
              <div className="w-10 h-10 bg-imperial-primary dark:bg-imperial-primary-light rounded-full flex items-center justify-center text-white font-semibold">
                IC
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          aria-hidden="true"
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  )
}
