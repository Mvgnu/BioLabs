'use client'
import { useState, useEffect } from 'react'

const steps = [
  'Welcome to BioLabs! Use the menu to navigate.',
  'Create inventory items and manage protocols easily.',
]

export default function Tour() {
  const [step, setStep] = useState(0)
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (localStorage.getItem('tour-complete') !== 'true') {
      setShow(true)
    }
  }, [])

  const next = () => {
    if (step + 1 < steps.length) {
      setStep(step + 1)
    } else {
      localStorage.setItem('tour-complete', 'true')
      setShow(false)
    }
  }

  if (!show) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white p-6 rounded shadow max-w-sm">
        <p className="mb-4">{steps[step]}</p>
        <button className="bg-blue-600 text-white px-4 py-2" onClick={next}>
          {step + 1 === steps.length ? 'Finish' : 'Next'}
        </button>
      </div>
    </div>
  )
}
