import type { Editor } from '@tiptap/react'
import { useEditorState } from '@tiptap/react'

interface ToolbarProps {
  editor: Editor
  onComment: () => void
}

interface ToolProps {
  label: string
  title: string
  active?: boolean
  disabled?: boolean
  onClick: () => void
}

function Tool({ label, title, active, disabled, onClick }: ToolProps) {
  return (
    <button
      className={`tool-button${active ? ' active' : ''}`}
      type="button"
      title={title}
      aria-label={title}
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
    >
      {label}
    </button>
  )
}

export function Toolbar({ editor, onComment }: ToolbarProps) {
  const state = useEditorState({
    editor,
    selector: ({ editor: current }) => ({
      bold: current.isActive('bold'),
      italic: current.isActive('italic'),
      strike: current.isActive('strike'),
      heading: current.isActive('heading', { level: 2 }),
      bullet: current.isActive('bulletList'),
      ordered: current.isActive('orderedList'),
      quote: current.isActive('blockquote'),
      canUndo: current.can().undo(),
      canRedo: current.can().redo(),
      hasSelection: !current.state.selection.empty,
    }),
  })

  const setLink = () => {
    const previous = editor.getAttributes('link').href as string | undefined
    const href = window.prompt('Link URL', previous ?? 'https://')
    if (href === null) return
    if (!href) editor.chain().focus().unsetLink().run()
    else editor.chain().focus().extendMarkRange('link').setLink({ href }).run()
  }

  return (
    <div className="toolbar" role="toolbar" aria-label="Text formatting">
      <div className="tool-group">
        <Tool label="↶" title="Undo my last change" disabled={!state.canUndo} onClick={() => editor.chain().focus().undo().run()} />
        <Tool label="↷" title="Redo my last change" disabled={!state.canRedo} onClick={() => editor.chain().focus().redo().run()} />
      </div>
      <div className="tool-group">
        <select
          className="style-select"
          aria-label="Text style"
          value={state.heading ? 'heading' : 'paragraph'}
          onChange={(event) => event.target.value === 'heading'
            ? editor.chain().focus().toggleHeading({ level: 2 }).run()
            : editor.chain().focus().setParagraph().run()}
        >
          <option value="paragraph">Body</option>
          <option value="heading">Heading</option>
        </select>
      </div>
      <div className="tool-group">
        <Tool label="B" title="Bold" active={state.bold} onClick={() => editor.chain().focus().toggleBold().run()} />
        <Tool label="I" title="Italic" active={state.italic} onClick={() => editor.chain().focus().toggleItalic().run()} />
        <Tool label="S" title="Strikethrough" active={state.strike} onClick={() => editor.chain().focus().toggleStrike().run()} />
        <Tool label="Link" title="Add link" active={editor.isActive('link')} onClick={setLink} />
      </div>
      <div className="tool-group">
        <Tool label="• List" title="Bulleted list" active={state.bullet} onClick={() => editor.chain().focus().toggleBulletList().run()} />
        <Tool label="1. List" title="Numbered list" active={state.ordered} onClick={() => editor.chain().focus().toggleOrderedList().run()} />
        <Tool label="❝" title="Block quote" active={state.quote} onClick={() => editor.chain().focus().toggleBlockquote().run()} />
      </div>
      <div className="tool-spacer" />
      <Tool label="Comment" title="Comment on selection" disabled={!state.hasSelection} onClick={onComment} />
    </div>
  )
}
