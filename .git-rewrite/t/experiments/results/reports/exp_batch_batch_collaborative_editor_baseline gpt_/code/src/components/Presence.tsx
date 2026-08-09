import type { ConnectionState, User } from '../types'

export function Presence({ users, connection }: { users: User[]; connection: ConnectionState }) {
  const label = connection === 'online' ? 'All changes synced' : connection === 'offline' ? 'Offline · changes saved locally' : 'Connecting…'
  return (
    <div className="presence">
      <span className={`sync-state ${connection}`}><i />{label}</span>
      <div className="avatar-stack" aria-label={`${users.length} collaborators present`}>
        {users.slice(0, 4).map((user) => (
          <span className="avatar" style={{ '--avatar-color': user.color } as React.CSSProperties} title={user.name} key={user.id}>
            {user.name.slice(0, 1).toUpperCase()}
          </span>
        ))}
        {users.length > 4 && <span className="avatar overflow">+{users.length - 4}</span>}
      </div>
    </div>
  )
}
