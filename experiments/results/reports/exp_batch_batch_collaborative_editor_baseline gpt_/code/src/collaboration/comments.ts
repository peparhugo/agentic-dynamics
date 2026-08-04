import type { Editor } from '@tiptap/react'
import { absolutePositionToRelativePosition, relativePositionToAbsolutePosition, ySyncPluginKey } from 'y-prosemirror'
import * as Y from 'yjs'
import type { CommentRecord, User } from '../types'
import type { CollaborationSession } from './session'

function encodePosition(position: Y.RelativePosition): string {
  const bytes = Y.encodeRelativePosition(position)
  let value = ''
  bytes.forEach((byte) => { value += String.fromCharCode(byte) })
  return btoa(value)
}

function decodePosition(value: string): Y.RelativePosition {
  const binary = atob(value)
  return Y.decodeRelativePosition(Uint8Array.from(binary, (char) => char.charCodeAt(0)))
}

function mappingFor(editor: Editor) {
  const pluginState = ySyncPluginKey.getState(editor.state)
  return pluginState.binding.mapping
}

export function addComment(
  session: CollaborationSession,
  editor: Editor,
  user: User,
  body: string,
): void {
  const { from, to } = editor.state.selection
  const mapping = mappingFor(editor)
  const map = new Y.Map<unknown>()
  const record: CommentRecord = {
    id: crypto.randomUUID(),
    author: user,
    body,
    createdAt: Date.now(),
    resolved: false,
    anchor: encodePosition(absolutePositionToRelativePosition(from, session.content, mapping)),
    head: encodePosition(absolutePositionToRelativePosition(to, session.content, mapping)),
  }
  session.doc.transact(() => {
    Object.entries(record).forEach(([key, value]) => map.set(key, value))
    session.comments.push([map])
  }, 'comment')
}

export function listComments(session: CollaborationSession): CommentRecord[] {
  return session.comments.toArray().map((comment) => comment.toJSON() as CommentRecord)
}

export function resolveComment(session: CollaborationSession, id: string): void {
  const comment = session.comments.toArray().find((entry) => entry.get('id') === id)
  session.doc.transact(() => comment?.set('resolved', true), 'comment')
}

export function focusComment(session: CollaborationSession, editor: Editor, comment: CommentRecord): void {
  const mapping = mappingFor(editor)
  const from = relativePositionToAbsolutePosition(session.doc, session.content, decodePosition(comment.anchor), mapping)
  const to = relativePositionToAbsolutePosition(session.doc, session.content, decodePosition(comment.head), mapping)
  if (from != null && to != null) editor.chain().focus().setTextSelection({ from, to }).run()
}
