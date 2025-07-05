'use client'
import Link from 'next/link'

export default function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="bg-white border-t border-neutral-200 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          {/* Brand */}
          <div className="col-span-1 md:col-span-2">
            <div className="flex items-center space-x-3 mb-4">
              <div className="w-8 h-8 bg-primary-500 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                </svg>
              </div>
              <span className="text-xl font-bold text-neutral-900">BioLab</span>
            </div>
            <p className="text-sm text-neutral-600 max-w-md leading-relaxed">
              Modern laboratory management system for research teams. 
              Streamline your inventory, protocols, and scientific workflows.
            </p>
          </div>

          {/* Quick Links */}
          <div>
            <h3 className="text-sm font-semibold text-neutral-900 mb-4">Features</h3>
            <ul className="space-y-3">
              <li>
                <Link href="/inventory" className="text-sm text-neutral-600 hover:text-primary-600 transition-colors">
                  Inventory Management
                </Link>
              </li>
              <li>
                <Link href="/protocols" className="text-sm text-neutral-600 hover:text-primary-600 transition-colors">
                  Protocol Templates
                </Link>
              </li>
              <li>
                <Link href="/notebook" className="text-sm text-neutral-600 hover:text-primary-600 transition-colors">
                  Lab Notebook
                </Link>
              </li>
              <li>
                <Link href="/analytics" className="text-sm text-neutral-600 hover:text-primary-600 transition-colors">
                  Analytics Dashboard
                </Link>
              </li>
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h3 className="text-sm font-semibold text-neutral-900 mb-4">Resources</h3>
            <ul className="space-y-3">
              <li>
                <Link href="/knowledge" className="text-sm text-neutral-600 hover:text-primary-600 transition-colors">
                  Knowledge Base
                </Link>
              </li>
              <li>
                <Link href="/troubleshooting" className="text-sm text-neutral-600 hover:text-primary-600 transition-colors">
                  Troubleshooting
                </Link>
              </li>
              <li>
                <Link href="/assistant" className="text-sm text-neutral-600 hover:text-primary-600 transition-colors">
                  Lab Assistant
                </Link>
              </li>
              <li>
                <Link href="/compliance" className="text-sm text-neutral-600 hover:text-primary-600 transition-colors">
                  Compliance
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="mt-8 pt-6 border-t border-neutral-200 flex flex-col sm:flex-row justify-between items-center">
          <p className="text-xs text-neutral-500">
            © {currentYear} BioLab. All rights reserved.
          </p>
          <div className="flex items-center space-x-6 mt-4 sm:mt-0">
            <Link href="/privacy" className="text-xs text-neutral-500 hover:text-neutral-600 transition-colors">
              Privacy Policy
            </Link>
            <Link href="/terms" className="text-xs text-neutral-500 hover:text-neutral-600 transition-colors">
              Terms of Service
            </Link>
          </div>
        </div>
      </div>
    </footer>
  )
}