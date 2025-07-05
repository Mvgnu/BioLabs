'use client'
import React from 'react'

interface AuthLayoutProps {
  children: React.ReactNode
  title: string
  subtitle: string
  backgroundGradient?: boolean
}

export default function AuthLayout({ 
  children, 
  title, 
  subtitle, 
  backgroundGradient = true 
}: AuthLayoutProps) {
  return (
    <div className={`min-h-screen flex ${backgroundGradient 
      ? 'bg-gradient-to-br from-primary-50 via-white to-secondary-50' 
      : 'bg-neutral-50'
    }`}>
      {/* Left Panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-600 to-primary-800"></div>
        <div className="relative z-10 flex flex-col justify-center px-12 text-white">
          {/* Logo */}
          <div className="flex items-center space-x-4 mb-8">
            <div className="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-xl flex items-center justify-center">
              <svg className="w-7 h-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
            </div>
            <span className="text-3xl font-bold">BioLab</span>
          </div>

          {/* Content */}
          <div className="max-w-md">
            <h1 className="text-4xl font-bold mb-6 leading-tight">
              Modern Laboratory
              <br />
              <span className="text-primary-200">Management</span>
            </h1>
            <p className="text-xl text-primary-100 leading-relaxed mb-8">
              Streamline your research with intelligent inventory management, 
              protocol automation, and collaborative workflows.
            </p>
            
            {/* Features */}
            <div className="space-y-4">
              {[
                { icon: '📊', text: 'Real-time analytics and insights' },
                { icon: '🔬', text: 'Protocol management and automation' },
                { icon: '📝', text: 'Digital lab notebook with compliance' },
                { icon: '🤝', text: 'Team collaboration and sharing' }
              ].map((feature, index) => (
                <div key={index} className="flex items-center space-x-3">
                  <span className="text-2xl">{feature.icon}</span>
                  <span className="text-primary-100">{feature.text}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Decorative Elements */}
          <div className="absolute top-10 right-10 w-32 h-32 bg-white/10 rounded-full blur-3xl"></div>
          <div className="absolute bottom-10 right-20 w-20 h-20 bg-secondary-400/30 rounded-full blur-2xl"></div>
        </div>
      </div>

      {/* Right Panel - Auth Form */}
      <div className="flex-1 flex items-center justify-center p-4 lg:p-8">
        <div className="w-full max-w-md">
          {/* Mobile Logo */}
          <div className="flex lg:hidden items-center justify-center space-x-3 mb-8">
            <div className="w-10 h-10 bg-primary-500 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
            </div>
            <span className="text-2xl font-bold text-neutral-900">BioLab</span>
          </div>

          {/* Header */}
          <div className="text-center mb-8">
            <h2 className="text-3xl font-bold text-neutral-900 mb-3">{title}</h2>
            <p className="text-neutral-600 text-lg">{subtitle}</p>
          </div>

          {/* Form Content */}
          {children}
        </div>
      </div>
    </div>
  )
}