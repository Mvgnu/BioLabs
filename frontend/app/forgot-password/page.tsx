'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import api from '../api/client'
import { Button, Input, Card, CardBody, Alert } from '../components/ui'
import AuthLayout from '../components/layout/AuthLayout'

export default function ForgotPasswordPage() {
  const [step, setStep] = useState<'request' | 'reset'>('request')
  const [email, setEmail] = useState('')
  const [token, setToken] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  const getPasswordStrength = (password: string) => {
    if (password.length === 0) return { score: 0, label: '', color: 'bg-neutral-200' }
    if (password.length < 6) return { score: 1, label: 'Weak', color: 'bg-error-500' }
    if (password.length < 8) return { score: 2, label: 'Fair', color: 'bg-warning-500' }
    if (password.length >= 8 && /[A-Z]/.test(password) && /[0-9]/.test(password)) {
      return { score: 4, label: 'Strong', color: 'bg-success-500' }
    }
    return { score: 3, label: 'Good', color: 'bg-info-500' }
  }

  const passwordStrength = getPasswordStrength(newPassword)

  const validateResetForm = () => {
    if (!token || !newPassword || !confirmPassword) {
      setError('All fields are required.')
      return false
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.')
      return false
    }
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.')
      return false
    }
    return true
  }

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)
    
    try {
      await api.post('/api/auth/request-password-reset', { email })
      setSuccess('Password reset instructions have been sent to your email address.')
      setStep('reset')
    } catch (err: any) {
      console.error(err)
      setError(err.response?.data?.detail || 'Failed to send reset instructions. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (!validateResetForm()) return

    setLoading(true)
    
    try {
      await api.post('/api/auth/reset-password', {
        token,
        new_password: newPassword
      })
      setSuccess('Password has been successfully reset. You can now sign in with your new password.')
      setTimeout(() => {
        router.push('/login')
      }, 2000)
    } catch (err: any) {
      console.error(err)
      setError(err.response?.data?.detail || 'Failed to reset password. Please check your token and try again.')
    } finally {
      setLoading(false)
    }
  }

  const isRequestFormValid = email && email.includes('@')
  const isResetFormValid = token && newPassword && confirmPassword && newPassword === confirmPassword && newPassword.length >= 8

  return (
    <AuthLayout
      title={step === 'request' ? 'Reset your password' : 'Enter reset code'}
      subtitle={step === 'request' 
        ? 'Enter your email to receive reset instructions' 
        : 'Enter the code from your email and create a new password'
      }
    >
      {/* Password Reset Form */}
      <Card variant="elevated" className="backdrop-blur-sm bg-white/95 border-0 shadow-2xl">
        <CardBody className="space-y-6 p-8">
          {error && (
            <Alert variant="error" dismissible onDismiss={() => setError('')}>
              {error}
            </Alert>
          )}

          {success && (
            <Alert variant="success" dismissible onDismiss={() => setSuccess('')}>
              {success}
            </Alert>
          )}

          {step === 'request' ? (
            <form onSubmit={handleRequestReset} className="space-y-5">
              <div className="space-y-4">
                <Input
                  type="email"
                  label="Email address"
                  placeholder="scientist@institution.edu"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                  autoFocus
                  helperText="We'll send reset instructions to this email address"
                  leftIcon={
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.32 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                    </svg>
                  }
                />
              </div>

              <Button 
                type="submit" 
                size="lg"
                className="w-full bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-700 hover:to-primary-800 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200"
                loading={loading}
                disabled={!isRequestFormValid}
              >
                {loading ? 'Sending instructions...' : 'Send reset instructions'}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleResetPassword} className="space-y-5">
              <div className="space-y-4">
                <Input
                  type="text"
                  label="Reset code"
                  placeholder="Enter the code from your email"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  required
                  autoComplete="off"
                  autoFocus
                  helperText="Enter the 6-digit code sent to your email"
                  leftIcon={
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" />
                    </svg>
                  }
                />

                <div>
                  <Input
                    type="password"
                    label="New password"
                    placeholder="Create a secure password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                    leftIcon={
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                      </svg>
                    }
                  />
                  {/* Password Strength Indicator */}
                  {newPassword && (
                    <div className="mt-2">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-neutral-500">Password strength</span>
                        <span className={`font-medium ${
                          passwordStrength.score <= 2 ? 'text-error-600' : 
                          passwordStrength.score === 3 ? 'text-warning-600' : 'text-success-600'
                        }`}>
                          {passwordStrength.label}
                        </span>
                      </div>
                      <div className="w-full bg-neutral-200 rounded-full h-2">
                        <div 
                          className={`h-2 rounded-full transition-all duration-300 ${passwordStrength.color}`}
                          style={{ width: `${(passwordStrength.score / 4) * 100}%` }}
                        ></div>
                      </div>
                      <p className="text-xs text-neutral-500 mt-1">
                        Use 8+ characters with uppercase, lowercase, and numbers
                      </p>
                    </div>
                  )}
                </div>

                <Input
                  type="password"
                  label="Confirm new password"
                  placeholder="Confirm your new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  error={confirmPassword && newPassword !== confirmPassword ? 'Passwords do not match' : ''}
                  leftIcon={
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  }
                />
              </div>

              <Button 
                type="submit" 
                size="lg"
                className="w-full bg-gradient-to-r from-secondary-600 to-secondary-700 hover:from-secondary-700 hover:to-secondary-800 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200"
                loading={loading}
                disabled={!isResetFormValid}
              >
                {loading ? 'Resetting password...' : 'Reset password'}
              </Button>
            </form>
          )}

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-neutral-200"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="bg-white px-4 text-neutral-500">Remember your password?</span>
            </div>
          </div>

          {/* Back to Login Link */}
          <div className="text-center">
            <Link 
              href="/login"
              className="inline-flex items-center space-x-2 text-sm font-medium text-neutral-700 hover:text-primary-600 transition-colors group"
            >
              <svg className="w-4 h-4 group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
              </svg>
              <span>Back to sign in</span>
            </Link>
          </div>
        </CardBody>
      </Card>

      {/* Security Notice */}
      <div className="mt-6 text-center">
        <p className="text-xs text-neutral-500 flex items-center justify-center space-x-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.623 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
          </svg>
          <span>Your password reset is secure and encrypted</span>
        </p>
      </div>
    </AuthLayout>
  )
} 