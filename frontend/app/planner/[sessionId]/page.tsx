'use client'

// purpose: render cloning planner wizard for a specific session id
// status: experimental

import React from 'react'

import { PlannerWizard } from '../components/PlannerWizard'

interface PlannerSessionPageProps {
  params: { sessionId: string }
}

const PlannerSessionPage: React.FC<PlannerSessionPageProps> = ({ params }) => {
  return <PlannerWizard sessionId={params.sessionId} />
}

export default PlannerSessionPage

