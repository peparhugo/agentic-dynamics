import Collaboration from '@tiptap/extension-collaboration'
import CollaborationCursor from '@tiptap/extension-collaboration-cursor'
import Highlight from '@tiptap/extension-highlight'
import Link from '@tiptap/extension-link'
import Placeholder from '@tiptap/extension-placeholder'
import TextAlign from '@tiptap/extension-text-align'
import StarterKit from '@tiptap/starter-kit'
import { useEditor } from '@tiptap/react'
import type { User } from '../types'
import type { CollaborationSession } from '../collaboration/session'

export function useCollaborativeEditor(session: CollaborationSession, user: User) {
  return useEditor({
    extensions: [
      StarterKit.configure({ history: false }),
      Highlight.configure({ multicolor: true }),
      Link.configure({ openOnClick: false, autolink: true }),
      TextAlign.configure({ types: ['heading', 'paragraph'] }),
      Placeholder.configure({ placeholder: 'Start writing together…' }),
      Collaboration.configure({ fragment: session.content }),
      CollaborationCursor.configure({
        provider: session.provider,
        user,
      }),
    ],
    editorProps: {
      attributes: {
        class: 'document-content',
        spellcheck: 'true',
        'aria-label': 'Document editor',
      },
    },
  })
}
