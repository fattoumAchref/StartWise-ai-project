'use client'

interface Props {
  taskState?: string
  agentLog?: string[]
}

const stateClass = (s?: string) => {
  switch (s) {
    case 'completed':      return 'state-completed'
    case 'working':        return 'state-working'
    case 'input-required': return 'state-input-required'
    case 'failed':         return 'state-failed'
    default:               return 'state-submitted'
  }
}

const stateIcon = (s?: string) => {
  switch (s) {
    case 'completed':      return '✅'
    case 'working':        return '⚙️'
    case 'input-required': return '❓'
    case 'failed':         return '❌'
    default:               return '⏳'
  }
}

export default function AgentActivity({ taskState, agentLog }: Props) {
  if (!taskState && (!agentLog || agentLog.length === 0)) return null

  return (
    <div style={{ fontSize: '.82rem' }}>
      {taskState && (
        <div style={{ marginBottom: '.6rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span>État Finance Agent :</span>
          <span className={`state-badge ${stateClass(taskState)}`}>
            {stateIcon(taskState)} {taskState}
          </span>
          {taskState === 'working' && <span className="spinner" />}
        </div>
      )}
      {agentLog && agentLog.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
          {agentLog.map((entry, i) => (
            <div key={i} style={{ display: 'flex', gap: '6px', color: '#6b7280', fontSize: '.77rem' }}>
              <span style={{ color: '#9ca3af', minWidth: 16 }}>{i + 1}.</span>
              <span>{entry}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
