import { useEffect, useState } from 'react'
import type { CommentRecord, ConnectionState, User } from '../types'
import { listComments } from '../collaboration/comments'
import { observeConnection, type CollaborationSession } from '../collaboration/session'

export function useSessionState(session: CollaborationSession) {
  const [connection, setConnection] = useState<ConnectionState>('connecting')
  const [comments, setComments] = useState<CommentRecord[]>(() => listComments(session))
  const [collaborators, setCollaborators] = useState<User[]>([])

  useEffect(() => observeConnection(session, setConnection), [session])

  useEffect(() => {
    const updateComments = () => setComments(listComments(session))
    session.comments.observeDeep(updateComments)
    updateComments()
    return () => session.comments.unobserveDeep(updateComments)
  }, [session])

  useEffect(() => {
    const updateUsers = () => {
      const users = [...session.provider.awareness.getStates().values()]
        .map((state) => state.user as User | undefined)
        .filter((user): user is User => Boolean(user))
      setCollaborators(users.filter((user, index) => users.findIndex(({ id }) => id === user.id) === index))
    }
    session.provider.awareness.on('change', updateUsers)
    updateUsers()
    return () => session.provider.awareness.off('change', updateUsers)
  }, [session])

  return { connection, comments, collaborators }
}
