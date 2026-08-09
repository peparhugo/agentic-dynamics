import type { VersionRecord } from '../types'

const endpoint = (documentId: string) => `/api/documents/${encodeURIComponent(documentId)}/versions`

export async function getVersions(documentId: string, signal?: AbortSignal): Promise<VersionRecord[]> {
  const response = await fetch(endpoint(documentId), { signal })
  if (!response.ok) throw new Error('Version history is unavailable')
  return response.json() as Promise<VersionRecord[]>
}

export async function createNamedVersion(documentId: string, label: string): Promise<VersionRecord> {
  const response = await fetch(endpoint(documentId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label }),
  })
  if (!response.ok) throw new Error('Could not create version')
  return response.json() as Promise<VersionRecord>
}

export async function restoreVersion(documentId: string, versionId: string): Promise<void> {
  const response = await fetch(`${endpoint(documentId)}/${encodeURIComponent(versionId)}/restore`, { method: 'POST' })
  if (!response.ok) throw new Error('Could not restore version')
}
