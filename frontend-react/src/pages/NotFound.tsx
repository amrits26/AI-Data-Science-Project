import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="container py-20 flex items-center justify-center min-h-screen">
      <div className="text-center max-w-md">
        <h1 className="text-6xl font-bold text-imperial-primary mb-4">404</h1>
        <h2 className="text-3xl font-bold text-gray-900 mb-3">Page Not Found</h2>
        <p className="text-gray-600 mb-8">
          Sorry, the page you're looking for doesn't exist. Let's get you back on track.
        </p>

        <Link to="/" className="btn btn-primary inline-flex items-center">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Dashboard
        </Link>
      </div>
    </div>
  )
}
