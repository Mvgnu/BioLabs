'use client'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  NodeChange,
  ReactFlowProvider,
  applyNodeChanges,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { GovernanceStageBlueprint } from '../../types'
import { Button, Card, CardBody, Input } from '../ui'

interface LadderBuilderProps {
  stages: GovernanceStageBlueprint[]
  onChange: (next: GovernanceStageBlueprint[]) => void
  defaultSLA?: number | null
}

const ROLE_PRESETS = [
  'scientist',
  'team_lead',
  'quality',
  'compliance',
  'executive',
]

const ensureNodeId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  return `stage-${Math.random().toString(36).slice(2)}`
}

const DEFAULT_HEIGHT = 120

function LadderBuilderInner({ stages, onChange, defaultSLA }: LadderBuilderProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null)

  useEffect(() => {
    const needsHydration = stages.some((stage) => !stage.metadata?.node_id)
    if (needsHydration) {
      const hydrated = stages.map((stage) => ({
        ...stage,
        metadata: {
          ...stage.metadata,
          node_id: stage.metadata?.node_id ?? ensureNodeId(),
        },
      }))
      onChange(hydrated)
    }
  }, [stages, onChange])

  const nodesInit = useMemo<Node[]>(() => {
    return stages.map((stage, index) => ({
      id: String(stage.metadata?.node_id ?? index),
      position: { x: 0, y: index * DEFAULT_HEIGHT },
      data: {
        label: stage.name || `${stage.required_role} stage`,
        stageId: stage.metadata?.node_id ?? String(index),
      },
      type: 'default',
    }))
  }, [stages])

  const edgesInit = useMemo<Edge[]>(() => {
    const edges: Edge[] = []
    for (let i = 0; i < stages.length - 1; i += 1) {
      const current = String(stages[i].metadata?.node_id ?? i)
      const next = String(stages[i + 1].metadata?.node_id ?? i + 1)
      edges.push({ id: `${current}-${next}`, source: current, target: next })
    }
    return edges
  }, [stages])

  const [nodes, setNodes] = useNodesState(nodesInit)
  const [edges, setEdges, handleEdgesChange] = useEdgesState(edgesInit)

  useEffect(() => {
    setNodes(nodesInit)
    setEdges(edgesInit)
  }, [nodesInit, edgesInit, setNodes, setEdges])

  const handleAddStage = useCallback(
    (role: string) => {
      const newStage: GovernanceStageBlueprint = {
        name: `${role.replace('_', ' ')} approval`,
        required_role: role,
        sla_hours: defaultSLA ?? null,
        metadata: {
          node_id: ensureNodeId(),
          palette_role: role,
        },
      }
      onChange([...stages, newStage])
      setSelectedId(String(newStage.metadata?.node_id))
    },
    [defaultSLA, onChange, stages]
  )

  const handleNodeChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => {
        const updated = applyNodeChanges(changes, nds)
        const didFinishDrag = changes.some(
          (change) => change.type === 'position' && change.dragging === false
        )
        if (didFinishDrag) {
          const ordered = [...updated].sort(
            (a, b) => (a.position?.y ?? 0) - (b.position?.y ?? 0)
          )
          const idToStage = new Map(
            stages.map((stage) => [String(stage.metadata?.node_id), stage])
          )
          const rehydrated = ordered
            .map((node) => idToStage.get(String(node.id)))
            .filter(Boolean) as GovernanceStageBlueprint[]
          if (rehydrated.length === stages.length) {
            onChange(rehydrated)
          }
        }
        return updated
      })
    },
    [handleNodesChange, onChange, stages]
  )

  const handleConnect = useCallback(
    (connection: Edge | Connection) => {
      setEdges((eds) => addEdge(connection, eds))
    },
    [setEdges]
  )

  const selectedStage = useMemo(() => {
    return stages.find((stage) => String(stage.metadata?.node_id) === selectedId) ?? null
  }, [stages, selectedId])

  const updateStage = useCallback(
    (partial: Partial<GovernanceStageBlueprint>) => {
      if (!selectedStage) return
      const next = stages.map((stage) => {
        if (stage.metadata?.node_id === selectedStage.metadata?.node_id) {
          return {
            ...stage,
            ...partial,
            metadata: {
              ...stage.metadata,
              ...partial.metadata,
              node_id: stage.metadata?.node_id,
            },
          }
        }
        return stage
      })
      onChange(next)
    },
    [onChange, selectedStage, stages]
  )

  const removeStage = useCallback(() => {
    if (!selectedStage) return
    const next = stages.filter(
      (stage) => stage.metadata?.node_id !== selectedStage.metadata?.node_id
    )
    onChange(next)
    setSelectedId(null)
  }, [onChange, selectedStage, stages])

  const slaTimeline = useMemo(() => {
    let cumulative = 0
    return stages.map((stage) => {
      const effective = stage.sla_hours ?? defaultSLA ?? 0
      cumulative += effective
      return {
        id: String(stage.metadata?.node_id),
        name: stage.name || stage.required_role,
        cumulative,
        stageSla: effective,
      }
    })
  }, [defaultSLA, stages])

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
      <Card className="lg:col-span-3">
        <CardBody>
          <div className="flex flex-col lg:flex-row gap-4">
            <div className="lg:w-60 space-y-3">
              <h3 className="text-sm font-semibold text-neutral-700">Stage Palette</h3>
              <div className="grid grid-cols-2 gap-2">
                {ROLE_PRESETS.map((role) => (
                  <Button key={role} variant="secondary" onClick={() => handleAddStage(role)}>
                    {role.replace('_', ' ')}
                  </Button>
                ))}
              </div>
              <div>
                <h4 className="text-xs uppercase tracking-wide text-neutral-500">
                  Timeline Preview
                </h4>
                <ol className="mt-2 space-y-2">
                  {slaTimeline.map((entry) => (
                    <li
                      key={entry.id}
                      className="flex items-center justify-between rounded border border-neutral-200 px-3 py-2 text-sm"
                    >
                      <span>{entry.name}</span>
                      <span className="text-neutral-500">{entry.cumulative}h</span>
                    </li>
                  ))}
                  {slaTimeline.length === 0 && (
                    <p className="text-neutral-500 text-sm">No stages yet</p>
                  )}
                </ol>
              </div>
            </div>
            <div className="flex-1 min-h-[320px] border border-neutral-200 rounded">
              <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={handleNodeChange}
                onEdgesChange={handleEdgesChange}
                onConnect={handleConnect}
                onNodeClick={(_, node) => setSelectedId(String(node.id))}
                fitView
                style={{ background: '#f9fafb', borderRadius: '0.5rem' }}
              >
                <MiniMap />
                <Controls />
                <Background gap={16} size={1} />
              </ReactFlow>
            </div>
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardBody className="space-y-3">
          <h3 className="text-sm font-semibold text-neutral-700">Stage Properties</h3>
          {selectedStage ? (
            <div className="space-y-3">
              <Input
                label="Stage name"
                value={selectedStage.name ?? ''}
                onChange={(event) =>
                  updateStage({ name: event.target.value || undefined })
                }
              />
              <Input
                label="Required role"
                value={selectedStage.required_role}
                onChange={(event) =>
                  updateStage({ required_role: event.target.value })
                }
              />
              <Input
                label="Stage SLA (hours)"
                type="number"
                value={selectedStage.sla_hours ?? ''}
                placeholder={defaultSLA?.toString() ?? '0'}
                onChange={(event) => {
                  const value = event.target.value
                  updateStage({ sla_hours: value ? Number(value) : null })
                }}
              />
              <div className="flex justify-between">
                <Button variant="ghost" onClick={removeStage}>
                  Remove stage
                </Button>
                <Button onClick={() => setSelectedId(null)}>Deselect</Button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-neutral-500">
              Select a stage node to edit its properties.
            </p>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

export default function LadderBuilder(props: LadderBuilderProps) {
  return (
    <ReactFlowProvider>
      <LadderBuilderInner {...props} />
    </ReactFlowProvider>
  )
}
