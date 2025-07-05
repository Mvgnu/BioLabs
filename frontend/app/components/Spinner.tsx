'use client'
import { Spinner } from './ui/Loading'

export default function SpinnerComponent() {
  return (
    <div className="flex justify-center items-center p-4" aria-label="Loading">
      <Spinner className="text-primary-500" />
    </div>
  )
}
