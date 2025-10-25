'use client'

import React, { useMemo } from 'react'
import {
  ArrowLeft,
  BellRing,
  Clock,
  Mail,
  Smartphone,
  ToggleLeft,
  ToggleRight,
  Waves,
  X,
} from 'lucide-react'

import { useNotifications } from '../../store/useNotifications'
import {
  useUpdateNotificationPreference,
  useUpdateNotificationSettings,
} from '../../hooks/useNotificationAPI'
import type { NotificationSettings } from '../../types/notifications'

// biolab-meta:
// purpose: Surface fine-grained notification preference controls inside the center drawer
// inputs: Zustand notification store state, preference and settings mutation hooks
// outputs: Persisted notification channel toggles, digest cadence, and quiet hour configuration
// status: active
// depends_on: frontend/app/store/useNotifications.ts, frontend/app/hooks/useNotificationAPI.ts
// related_docs: frontend/app/components/notifications/README.md

const channels = [
  { key: 'in_app', label: 'In-app', icon: BellRing },
  { key: 'email', label: 'Email', icon: Mail },
  { key: 'sms', label: 'SMS', icon: Smartphone },
] as const

const preferenceCatalog: Array<{
  prefType: string
  label: string
  description: string
}> = [
  {
    prefType: 'booking',
    label: 'Bookings',
    description: 'Resource reservations, confirmations, and cancellations.',
  },
  {
    prefType: 'inventory_alert',
    label: 'Inventory alerts',
    description: 'Low stock warnings and expiring reagent notices.',
  },
  {
    prefType: 'protocol_update',
    label: 'Protocol updates',
    description: 'Changes to SOPs, merges, and execution outcomes.',
  },
  {
    prefType: 'project_activity',
    label: 'Project activity',
    description: 'Task assignments, due dates, and collaboration pings.',
  },
  {
    prefType: 'system_alert',
    label: 'System alerts',
    description: 'Platform maintenance, downtime, and compliance notices.',
  },
]

const digestOptions: Array<{
  value: NotificationSettings['digest_frequency']
  label: string
  description: string
}> = [
  {
    value: 'immediate',
    label: 'Immediate',
    description: 'Receive every notification as it happens without batching.',
  },
  {
    value: 'hourly',
    label: 'Hourly',
    description: 'Roll-up unread events into hourly recaps.',
  },
  {
    value: 'daily',
    label: 'Daily',
    description: 'One digest per day summarizing your unread activity.',
  },
  {
    value: 'weekly',
    label: 'Weekly',
    description: 'Bundle notifications into a single weekly review.',
  },
]

interface NotificationSettingsPanelProps {
  onClose: () => void
}

const normalizeTime = (value?: string | null) => (value ? value.slice(0, 5) : '')

export const NotificationSettingsPanel: React.FC<NotificationSettingsPanelProps> = ({
  onClose,
}) => {
  const {
    preferences,
    settings,
    updatePreference,
    updateSettings,
  } = useNotifications()

  const updatePreferenceMutation = useUpdateNotificationPreference()
  const updateSettingsMutation = useUpdateNotificationSettings()

  const preferenceLookup = useMemo(() => {
    const map = new Map<string, Record<string, boolean>>()
    for (const pref of preferences) {
      const key = pref.pref_type
      if (!map.has(key)) {
        map.set(key, {})
      }
      map.get(key)![pref.channel] = pref.enabled
    }
    return map
  }, [preferences])

  const persistSettings = (partial: Partial<NotificationSettings>) => {
    const next = { ...settings, ...partial }
    updateSettings(partial)

    const payload: Partial<NotificationSettings> = {}

    if (Object.prototype.hasOwnProperty.call(partial, 'digest_frequency')) {
      payload.digest_frequency = next.digest_frequency
    }

    if (Object.prototype.hasOwnProperty.call(partial, 'quiet_hours_enabled')) {
      payload.quiet_hours_enabled = next.quiet_hours_enabled
    }

    if (
      Object.prototype.hasOwnProperty.call(partial, 'quiet_hours_start') ||
      Object.prototype.hasOwnProperty.call(partial, 'quiet_hours_end')
    ) {
      if (next.quiet_hours_start) {
        payload.quiet_hours_start = next.quiet_hours_start
      }
      if (next.quiet_hours_end) {
        payload.quiet_hours_end = next.quiet_hours_end
      }
    }

    if (next.quiet_hours_enabled) {
      payload.quiet_hours_enabled = next.quiet_hours_enabled
      if (next.quiet_hours_start) {
        payload.quiet_hours_start = next.quiet_hours_start
      }
      if (next.quiet_hours_end) {
        payload.quiet_hours_end = next.quiet_hours_end
      }
    }

    updateSettingsMutation.mutate(payload)
  }

  const handleChannelToggle = (prefType: string, channel: string, enabled: boolean) => {
    updatePreference(prefType, channel, enabled)
    updatePreferenceMutation.mutate({ prefType, channel, enabled })
  }

  const handleDigestChange = (value: NotificationSettings['digest_frequency']) => {
    persistSettings({ digest_frequency: value })
  }

  const handleQuietToggle = (enabled: boolean) => {
    const defaults: Partial<NotificationSettings> = {
      quiet_hours_enabled: enabled,
    }

    if (enabled) {
      defaults.quiet_hours_start = settings.quiet_hours_start || '21:00'
      defaults.quiet_hours_end = settings.quiet_hours_end || '07:00'
    }

    persistSettings(defaults)
  }

  const handleQuietTimeChange = (field: 'quiet_hours_start' | 'quiet_hours_end', value: string) => {
    if (!value) {
      persistSettings({ quiet_hours_enabled: false, [field]: null })
      return
    }

    persistSettings({ [field]: value })
  }

  return (
    <div className="absolute inset-0 bg-white">
      <div className="flex items-center justify-between border-b border-neutral-200 px-4 py-3">
        <div className="flex items-center space-x-2">
          <button
            onClick={onClose}
            className="flex items-center space-x-1 rounded-md border border-neutral-200 bg-white px-2 py-1 text-sm text-neutral-600 hover:bg-neutral-50"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back</span>
          </button>
          <div>
            <p className="text-sm font-semibold text-neutral-900">Notification preferences</p>
            <p className="text-xs text-neutral-500">Control delivery channels, digest cadence, and quiet windows.</p>
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label="Close notification settings"
          className="rounded-full p-1 text-neutral-500 hover:bg-neutral-100 hover:text-neutral-700"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="flex h-[calc(100%-3.5rem)] flex-col overflow-y-auto px-4 py-4 space-y-6">
        <section className="rounded-lg border border-neutral-200 bg-white shadow-sm">
          <header className="flex items-start space-x-3 border-b border-neutral-200 px-4 py-3">
            <BellRing className="mt-1 h-5 w-5 text-primary-500" />
            <div>
              <h2 className="text-sm font-semibold text-neutral-900">Digest cadence</h2>
              <p className="text-xs text-neutral-500">Choose how often BioLab bundles unread notifications into email digests.</p>
            </div>
          </header>
          <div className="space-y-2 px-4 py-3">
            {digestOptions.map((option) => (
              <label
                key={option.value}
                className={`flex cursor-pointer items-start space-x-3 rounded-md border px-3 py-2 text-sm transition-colors ${
                  settings.digest_frequency === option.value
                    ? 'border-primary-400 bg-primary-50'
                    : 'border-neutral-200 hover:border-primary-200 hover:bg-neutral-50'
                }`}
              >
                <input
                  type="radio"
                  name="digest-frequency"
                  className="mt-1"
                  value={option.value}
                  checked={settings.digest_frequency === option.value}
                  onChange={() => handleDigestChange(option.value)}
                />
                <div>
                  <p className="font-medium text-neutral-800">{option.label}</p>
                  <p className="text-xs text-neutral-500">{option.description}</p>
                </div>
              </label>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-neutral-200 bg-white shadow-sm">
          <header className="flex items-start space-x-3 border-b border-neutral-200 px-4 py-3">
            <Clock className="mt-1 h-5 w-5 text-primary-500" />
            <div>
              <h2 className="text-sm font-semibold text-neutral-900">Quiet hours</h2>
              <p className="text-xs text-neutral-500">Pause outbound channels during focus blocks or overnight windows.</p>
            </div>
          </header>
          <div className="space-y-4 px-4 py-4">
            <button
              onClick={() => handleQuietToggle(!settings.quiet_hours_enabled)}
              className="flex w-full items-center justify-between rounded-md border border-neutral-200 bg-white px-3 py-2 text-left text-sm text-neutral-700 hover:border-primary-200 hover:bg-neutral-50"
            >
              <span className="font-medium">Quiet hours {settings.quiet_hours_enabled ? 'enabled' : 'disabled'}</span>
              {settings.quiet_hours_enabled ? (
                <ToggleRight className="h-5 w-5 text-primary-500" />
              ) : (
                <ToggleLeft className="h-5 w-5 text-neutral-400" />
              )}
            </button>

            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col text-xs font-medium text-neutral-600">
                Start
                <input
                  type="time"
                  value={normalizeTime(settings.quiet_hours_start)}
                  disabled={!settings.quiet_hours_enabled}
                  onChange={(event) => handleQuietTimeChange('quiet_hours_start', event.target.value)}
                  className="mt-1 rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-800 shadow-sm disabled:bg-neutral-100"
                />
              </label>
              <label className="flex flex-col text-xs font-medium text-neutral-600">
                End
                <input
                  type="time"
                  value={normalizeTime(settings.quiet_hours_end)}
                  disabled={!settings.quiet_hours_enabled}
                  onChange={(event) => handleQuietTimeChange('quiet_hours_end', event.target.value)}
                  className="mt-1 rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-800 shadow-sm disabled:bg-neutral-100"
                />
              </label>
            </div>
          </div>
        </section>

        <section className="rounded-lg border border-neutral-200 bg-white shadow-sm">
          <header className="flex items-start space-x-3 border-b border-neutral-200 px-4 py-3">
            <Waves className="mt-1 h-5 w-5 text-primary-500" />
            <div>
              <h2 className="text-sm font-semibold text-neutral-900">Channel routing</h2>
              <p className="text-xs text-neutral-500">Decide which surfaces carry different BioLab notification categories.</p>
            </div>
          </header>
          <div className="space-y-4 px-4 py-4">
            {preferenceCatalog.map((pref) => {
              const channelState = preferenceLookup.get(pref.prefType) || {}
              return (
                <div key={pref.prefType} className="rounded-md border border-neutral-200 p-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm font-medium text-neutral-800">{pref.label}</p>
                      <p className="text-xs text-neutral-500">{pref.description}</p>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 md:grid-cols-3">
                    {channels.map(({ key, label, icon: Icon }) => {
                      const enabled = channelState[key] ?? true
                      return (
                        <button
                          key={key}
                          onClick={() => handleChannelToggle(pref.prefType, key, !enabled)}
                          className={`flex items-center justify-between rounded-md border px-3 py-2 text-sm transition-colors ${
                            enabled
                              ? 'border-primary-300 bg-primary-50 text-primary-700'
                              : 'border-neutral-200 bg-white text-neutral-500 hover:border-primary-200 hover:text-primary-600'
                          }`}
                        >
                          <span className="flex items-center space-x-2">
                            <Icon className="h-4 w-4" />
                            <span>{label}</span>
                          </span>
                          <span className="text-xs font-medium">{enabled ? 'On' : 'Off'}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      </div>
    </div>
  )
}
