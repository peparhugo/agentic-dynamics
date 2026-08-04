import { useEffect, useState } from 'react'
import { createNamedVersion, getVersions, restoreVersion } from '../api/versions'
import type { VersionRecord } from '../types'

export function VersionPanel({ documentId, onClose }: { documentId: string; onClose: () => void }) {
  const [versions, setVersions] = useState<VersionRecord[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getVersions(documentId, controller.signal).then(setVersions).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Version history is unavailable')
    })
    return () => controller.abort()
  }, [documentId])

  const nameCurrent = async () => {
    const label = window.prompt('Name this version')?.trim()
    if (!label) return
    setBusy(true)
    try {
      const version = await createNamedVersion(documentId, label)
      setVersions((current) => [version, ...current])
      setError('')
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not create version') }
    finally { setBusy(false) }
  }

  return (
    <aside className="side-panel" aria-label="Version history">
      <header className="panel-header"><div><span className="eyebrow">Document</span><h2>Version history</h2></div><button onClick={onClose} aria-label="Close history">×</button></header>
      <button className="primary-button wide" disabled={busy} onClick={nameCurrent}>Name current version</button>
      {error && <p className="panel-error">{error}</p>}
      <div className="version-list">
        {versions.map((version) => (
          <article className="version-card" key={version.id}>
            <time>{new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(new Date(version.createdAt))}</time>
            <h3>{version.label}</h3><p>{version.author.name} · {version.preview}</p>
            <button className="restore-button" onClick={() => void restoreVersion(documentId, version.id).catch(() => setError('Could not restore version'))}>Restore this version</button>
          </article>
        ))}
        {!versions.length && !error && <div className="empty-state"><span>◷</span><h3>Loading history</h3></div>}
      </div>
    </aside>
  )
}
