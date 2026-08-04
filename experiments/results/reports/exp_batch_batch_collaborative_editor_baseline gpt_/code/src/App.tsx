import { EditorContent } from '@tiptap/react'
import { useEffect, useState } from 'react'
import { CommentsPanel } from './components/CommentsPanel'
import { Presence } from './components/Presence'
import { Toolbar } from './components/Toolbar'
import { VersionPanel } from './components/VersionPanel'
import { createCollaborationSession } from './collaboration/session'
import { useCollaborativeEditor } from './hooks/useCollaborativeEditor'
import { useSessionState } from './hooks/useSessionState'
import type { SidePanel, User } from './types'

const COLORS = ['#cf4f34', '#307a78', '#8257a6', '#b37a1d']

function loadUser(): User {
  const existing = localStorage.getItem('relay-user')
  if (existing) return JSON.parse(existing) as User
  const id = crypto.randomUUID()
  const user = { id, name: `Guest ${id.slice(0, 4)}`, color: COLORS[Math.floor(Math.random() * COLORS.length)] }
  localStorage.setItem('relay-user', JSON.stringify(user))
  return user
}

export default function App() {
  const [user] = useState(loadUser)
  const documentId = new URLSearchParams(location.search).get('document') ?? 'product-brief'
  const [session] = useState(() => createCollaborationSession(documentId, user))
  const editor = useCollaborativeEditor(session, user)
  const { connection, comments, collaborators } = useSessionState(session)
  const [panel, setPanel] = useState<SidePanel>(null)
  const [composingComment, setComposingComment] = useState(false)
  const [title, setTitle] = useState('The future of focused work')

  useEffect(() => () => session.destroy(), [session])

  if (!editor) return <main className="loading-screen">Preparing your workspace…</main>

  const beginComment = () => { setPanel('comments'); setComposingComment(true) }
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Relay home"><span>R</span>Relay</a>
        <div className="document-heading">
          <input aria-label="Document title" value={title} onChange={(event) => setTitle(event.target.value)} />
          <div><span>Workspace / Product</span><span className="saved-label">Auto-saved</span></div>
        </div>
        <Presence users={collaborators} connection={connection} />
        <button className={`topbar-button${panel === 'comments' ? ' active' : ''}`} onClick={() => setPanel(panel === 'comments' ? null : 'comments')}>Comments <b>{comments.filter(({ resolved }) => !resolved).length}</b></button>
        <button className={`topbar-button icon-only${panel === 'history' ? ' active' : ''}`} title="Version history" aria-label="Version history" onClick={() => setPanel(panel === 'history' ? null : 'history')}>◷</button>
        <button className="share-button">Share</button>
      </header>
      <Toolbar editor={editor} onComment={beginComment} />
      <main className="workspace">
        <div className="page-wrap">
          <div className="page-meta"><span>PRODUCT STRATEGY</span><span>Updated just now</span></div>
          <EditorContent editor={editor} />
          <div className="page-footer"><span>Relay workspace</span><span>1</span></div>
        </div>
        {panel === 'comments' && <CommentsPanel session={session} editor={editor} user={user} comments={comments} composing={composingComment} onComposingChange={setComposingComment} onClose={() => setPanel(null)} />}
        {panel === 'history' && <VersionPanel documentId={documentId} onClose={() => setPanel(null)} />}
      </main>
    </div>
  )
}
