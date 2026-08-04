import { useState } from 'react'
import type { Editor } from '@tiptap/react'
import type { CommentRecord, User } from '../types'
import type { CollaborationSession } from '../collaboration/session'
import { addComment, focusComment, resolveComment } from '../collaboration/comments'

interface Props {
  session: CollaborationSession
  editor: Editor
  user: User
  comments: CommentRecord[]
  composing: boolean
  onClose: () => void
  onComposingChange: (value: boolean) => void
}

export function CommentsPanel({ session, editor, user, comments, composing, onClose, onComposingChange }: Props) {
  const [body, setBody] = useState('')
  const openComments = comments.filter(({ resolved }) => !resolved)

  const submit = () => {
    const text = body.trim()
    if (!text) return
    addComment(session, editor, user, text)
    setBody('')
    onComposingChange(false)
  }

  return (
    <aside className="side-panel" aria-label="Comments">
      <header className="panel-header"><div><span className="eyebrow">Discussion</span><h2>Comments</h2></div><button onClick={onClose} aria-label="Close comments">×</button></header>
      {composing && (
        <div className="comment-composer">
          <p>Comment on the selected text</p>
          <textarea autoFocus value={body} onChange={(event) => setBody(event.target.value)} placeholder="Add your thoughts…" />
          <div><button className="ghost-button" onClick={() => onComposingChange(false)}>Cancel</button><button className="primary-button" onClick={submit}>Comment</button></div>
        </div>
      )}
      <div className="comment-list">
        {openComments.map((comment) => (
          <article className="comment-card" key={comment.id} onClick={() => focusComment(session, editor, comment)}>
            <div className="comment-meta"><span className="avatar small" style={{ '--avatar-color': comment.author.color } as React.CSSProperties}>{comment.author.name[0]}</span><strong>{comment.author.name}</strong><time>{new Intl.RelativeTimeFormat('en', { numeric: 'auto' }).format(Math.round((comment.createdAt - Date.now()) / 60000), 'minute')}</time></div>
            <p>{comment.body}</p>
            <button className="resolve-button" onClick={(event) => { event.stopPropagation(); resolveComment(session, comment.id) }}>Resolve</button>
          </article>
        ))}
        {!openComments.length && !composing && <div className="empty-state"><span>✓</span><h3>No open threads</h3><p>Select text in the document to start a conversation.</p></div>}
      </div>
    </aside>
  )
}
