'use client'
import { useState } from 'react'
import { useProjects, useCreateProject, useProjectTasks, useCreateTask, useUpdateTask, useDeleteTask } from '../hooks/useProjects'

export default function ProjectsPage() {
  const { data: projects } = useProjects()
  const createProject = useCreateProject()
  const [selected, setSelected] = useState<string | null>(null)
  const { data: tasks } = useProjectTasks(selected ?? '')
  const createTask = useCreateTask(selected ?? '')
  const updateTask = useUpdateTask(selected ?? '')
  const deleteTask = useDeleteTask(selected ?? '')

  const [name, setName] = useState('')
  const [taskName, setTaskName] = useState('')

  const addProject = () => {
    createProject.mutate({ name })
    setName('')
  }

  const addTask = () => {
    if (!selected) return
    createTask.mutate({ name: taskName })
    setTaskName('')
  }

  return (
    <div>
      <h1 className="text-xl mb-4">Projects</h1>
      <div className="mb-4">
        <input className="border p-1 mr-2" value={name} onChange={(e) => setName(e.target.value)} />
        <button onClick={addProject}>Add Project</button>
      </div>
      <ul className="space-y-2 mb-6">
        {projects?.map((p) => (
          <li key={p.id} className="border p-2 cursor-pointer" onClick={() => setSelected(p.id)}>
            {p.name}
          </li>
        ))}
      </ul>
      {selected && (
        <div>
          <h2 className="text-lg mb-2">Tasks</h2>
          <div className="mb-2">
            <input className="border p-1 mr-2" value={taskName} onChange={(e) => setTaskName(e.target.value)} />
            <button onClick={addTask}>Add Task</button>
          </div>
          <ul className="space-y-2">
            {tasks?.map((t) => (
              <li key={t.id} className="border p-2 flex justify-between">
                <span>
                  {t.name} - {t.status}
                </span>
                <span className="space-x-2">
                  <button onClick={() => updateTask.mutate({ id: t.id, data: { status: 'done' } })}>Done</button>
                  <button onClick={() => deleteTask.mutate(t.id)}>Delete</button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
