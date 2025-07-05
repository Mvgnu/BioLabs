'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import api from '../api/client'
import { useAuth } from '../store/useAuth'
import { Button, Input, Card, CardBody, Alert } from '../components/ui'
import AuthLayout from '../components/layout/AuthLayout'

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [acceptedTerms, setAcceptedTerms] = useState(false)
  const router = useRouter()
  const setToken = useAuth((s) => s.setToken)

  const getPasswordStrength = (password: string) => {
    if (password.length === 0) return { score: 0, label: '', color: 'bg-neutral-200' }
    if (password.length < 6) return { score: 1, label: 'Weak', color: 'bg-error-500' }
    if (password.length < 8) return { score: 2, label: 'Fair', color: 'bg-warning-500' }
    if (password.length >= 8 && /[A-Z]/.test(password) && /[0-9]/.test(password)) {
      return { score: 4, label: 'Strong', color: 'bg-success-500' }
    }
    return { score: 3, label: 'Good', color: 'bg-info-500' }
  }

  const passwordStrength = getPasswordStrength(password)

  const validateForm = () => {
    if (!email || !password || !confirmPassword) {
      setError('All fields are required.')
      return false
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return false
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return false
    }
    if (!acceptedTerms) {
      setError('Please accept the terms and conditions.')
      return false
    }
    return true
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!validateForm()) return

    setLoading(true)
    
    try {
      const resp = await api.post('/api/auth/register', { email, password })
      const token = resp.data.access_token
      setToken(token)
      router.push('/')
    } catch (err: any) {
      console.error(err)
      setError(err.response?.data?.detail || 'Registration failed. Email may already be in use.')
    } finally {
      setLoading(false)
    }
  }

  const isFormValid = email && password && confirmPassword && password === confirmPassword && acceptedTerms && password.length >= 8

  return (
    <AuthLayout
      title="Join BioLab"
      subtitle="Start your research journey today"
    >
      {/* Registration Form */}
      <Card variant="elevated" className="backdrop-blur-sm bg-white/95 border-0 shadow-2xl">
        <CardBody className="space-y-6 p-8">
          {error && (
            <Alert variant="error" dismissible onDismiss={() => setError('')}>
              {error}
            </Alert>
          )}

          <form onSubmit={submit} className="space-y-5">
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
                helperText="Use your institutional or professional email"
                leftIcon={
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.32 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
                  </svg>
                }
              />

              <div>
                <Input
                  type="password"
                  label="Password"
                  placeholder="Create a secure password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  leftIcon={
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                    </svg>
                  }
                />
                {/* Password Strength Indicator */}
                {password && (
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
                label="Confirm password"
                placeholder="Confirm your password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
                error={confirmPassword && password !== confirmPassword ? 'Passwords do not match' : ''}
                leftIcon={
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                }
              />
            </div>

            {/* Terms and Conditions */}
            <div className="flex items-start space-x-3">
              <input
                type="checkbox"
                id="terms"
                checked={acceptedTerms}
                onChange={(e) => setAcceptedTerms(e.target.checked)}
                className="mt-0.5 w-4 h-4 text-primary-600 bg-white border-neutral-300 rounded focus:ring-primary-500 focus:ring-2"
                required
              />
              <label htmlFor="terms" className="text-sm text-neutral-600 leading-relaxed">
                I agree to the{' '}
                <Link href="/terms" className="text-primary-600 hover:text-primary-700 font-medium">
                  Terms of Service
                </Link>{' '}
                and{' '}
                <Link href="/privacy" className="text-primary-600 hover:text-primary-700 font-medium">
                  Privacy Policy
                </Link>
              </label>
            </div>

            <Button 
              type="submit" 
              size="lg"
              className="w-full bg-gradient-to-r from-secondary-600 to-secondary-700 hover:from-secondary-700 hover:to-secondary-800 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200"
              loading={loading}
              disabled={!isFormValid}
            >
              {loading ? 'Creating your account...' : 'Create BioLab account'}
            </Button>
          </form>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-neutral-200"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="bg-white px-4 text-neutral-500">Already have an account?</span>
            </div>
          </div>

          {/* Login Link */}
          <div className="text-center">
            <Link 
              href="/login"
              className="inline-flex items-center space-x-2 text-sm font-medium text-neutral-700 hover:text-primary-600 transition-colors group"
            >
              <svg className="w-4 h-4 group-hover:-translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
              </svg>
              <span>Sign in to existing account</span>
            </Link>
          </div>
        </CardBody>
      </Card>

      {/* Benefits */}
      <div className="mt-6 grid grid-cols-2 gap-4 text-center">
        <div className="bg-white/80 backdrop-blur-sm rounded-lg p-4">
          <div className="text-2xl mb-2">🔒</div>
          <p className="text-xs text-neutral-600">Secure & Compliant</p>
        </div>
        <div className="bg-white/80 backdrop-blur-sm rounded-lg p-4">
          <div className="text-2xl mb-2">🚀</div>
          <p className="text-xs text-neutral-600">Start Immediately</p>
        </div>
      </div>
    </AuthLayout>
  )
}
