'use client'
import { ReactNode, useMemo } from 'react'
import Link from 'next/link'
import { useCurrentUser } from '../hooks/useCurrentUser'
import { Alert, Card, CardBody, LoadingState } from '../components/ui'

interface GovernanceLayoutProps {
  children: ReactNode
}

// purpose: enforce admin-only access for governance workspace routes
// inputs: authenticated user identity via useCurrentUser
// outputs: guarded layout shell rendering content for admins only
// status: experimental
export default function GovernanceLayout({ children }: GovernanceLayoutProps) {
  const { data: user, isLoading } = useCurrentUser()

  const guardState = useMemo(() => {
    if (isLoading) return 'loading' as const
    if (!user) return 'unauthenticated' as const
    if (!user.is_admin) return 'forbidden' as const
    return 'ready' as const
  }, [isLoading, user])

  if (guardState === 'loading') {
    return (
      <div className="p-8">
        <LoadingState message="Checking admin access" />
      </div>
    )
  }

  if (guardState === 'unauthenticated') {
    return (
      <div className="max-w-2xl mx-auto py-12">
        <Card>
          <CardBody className="space-y-4">
            <Alert variant="warning" title="Login required">
              <p>You need to sign in before accessing the governance workspace.</p>
            </Alert>
            <Link
              href="/login"
              className="inline-flex items-center justify-center rounded-md bg-primary-500 px-4 py-3 text-sm font-medium text-white transition hover:bg-primary-600"
            >
              Go to login
            </Link>
          </CardBody>
        </Card>
      </div>
    )
  }

  if (guardState === 'forbidden') {
    return (
      <div className="max-w-2xl mx-auto py-12">
        <Card>
          <CardBody className="space-y-4">
            <Alert variant="error" title="Insufficient privileges">
              <p>
                Your account is not configured as an admin. Contact the governance admin team to
                request access.
              </p>
            </Alert>
            <Link
              href="/"
              className="inline-flex items-center justify-center rounded-md border border-primary-500 px-4 py-3 text-sm font-medium text-primary-600 transition hover:bg-primary-50"
            >
              Return home
            </Link>
          </CardBody>
        </Card>
      </div>
    )
  }

  return <div className="p-6 space-y-6">{children}</div>
}
