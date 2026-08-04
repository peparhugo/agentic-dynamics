import { IndexeddbPersistence } from 'y-indexeddb'
import { WebsocketProvider } from 'y-websocket'
import * as Y from 'yjs'
import type { ConnectionState, User } from '../types'

const DEFAULT_WS_URL = 'ws://localhost:1234'

export interface CollaborationSession {
  doc: Y.Doc
  provider: WebsocketProvider
  persistence: IndexeddbPersistence
  content: Y.XmlFragment
  comments: Y.Array<Y.Map<unknown>>
  destroy: () => void
}

export function createCollaborationSession(documentId: string, user: User): CollaborationSession {
  const doc = new Y.Doc()
  const persistence = new IndexeddbPersistence(`relay:${documentId}`, doc)
  const provider = new WebsocketProvider(
    import.meta.env.VITE_COLLABORATION_URL ?? DEFAULT_WS_URL,
    documentId,
    doc,
    { connect: navigator.onLine },
  )

  provider.awareness.setLocalStateField('user', user)

  const onOnline = () => provider.connect()
  const onOffline = () => provider.disconnect()
  window.addEventListener('online', onOnline)
  window.addEventListener('offline', onOffline)

  return {
    doc,
    provider,
    persistence,
    content: doc.getXmlFragment('document'),
    comments: doc.getArray<Y.Map<unknown>>('comments'),
    destroy() {
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
      provider.destroy()
      persistence.destroy()
      doc.destroy()
    },
  }
}

export function observeConnection(
  session: CollaborationSession,
  listener: (state: ConnectionState) => void,
): () => void {
  const statusHandler = ({ status }: { status: 'connecting' | 'connected' | 'disconnected' }) => {
    listener(status === 'connected' ? 'online' : navigator.onLine ? 'connecting' : 'offline')
  }
  const onlineHandler = () => listener('connecting')
  const offlineHandler = () => listener('offline')

  session.provider.on('status', statusHandler)
  window.addEventListener('online', onlineHandler)
  window.addEventListener('offline', offlineHandler)
  listener(navigator.onLine ? 'connecting' : 'offline')

  return () => {
    session.provider.off('status', statusHandler)
    window.removeEventListener('online', onlineHandler)
    window.removeEventListener('offline', offlineHandler)
  }
}
