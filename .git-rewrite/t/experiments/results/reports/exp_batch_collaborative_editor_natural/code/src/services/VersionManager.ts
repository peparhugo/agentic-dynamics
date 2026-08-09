import type { VersionEntry, VersionDiff } from '@/types/version';
import type { DocumentSnapshot } from '@/types/editor';
import { v4 as uuid } from 'uuid';
import { IndexedDBManager } from './IndexedDBManager';

export class VersionManager {
  private versions: VersionEntry[] = [];
  private idb: IndexedDBManager;

  constructor() {
    this.idb = new IndexedDBManager('collab-editor');
  }

  async init(): Promise<void> {
    await this.idb.init();
    const stored = await this.idb.getVersions();
    if (stored.length > 0) {
      this.versions = stored.map(s => ({
        id: s.id,
        version: s.version,
        timestamp: s.timestamp,
        author: s.author,
        message: s.message,
        snapshot: JSON.parse(s.snapshot) as DocumentSnapshot,
        isAutoSave: s.message === 'Auto-save',
      }));
    }
  }

  saveVersion(snapshot: DocumentSnapshot, author: string, message?: string): VersionEntry {
    const entry: VersionEntry = {
      id: uuid(),
      version: this.versions.length + 1,
      timestamp: Date.now(),
      author,
      message: message || 'Manual save',
      snapshot,
      isAutoSave: !message,
    };
    this.versions.push(entry);
    this.idb.saveVersion({
      id: entry.id,
      version: entry.version,
      snapshot: JSON.stringify(entry.snapshot),
      timestamp: entry.timestamp,
      author: entry.author,
      message: entry.message,
    });
    return entry;
  }

  getAll(): VersionEntry[] {
    return [...this.versions].sort((a, b) => b.version - a.version);
  }

  getByVersion(version: number): VersionEntry | undefined {
    return this.versions.find(v => v.version === version);
  }

  diff(fromVersion: number, toVersion: number): VersionDiff {
    const from = this.getByVersion(fromVersion);
    const to = this.getByVersion(toVersion);
    if (!from || !to) {
      return { fromVersion, toVersion, changes: [] };
    }
    return computeDiff(from.snapshot, to.snapshot, fromVersion, toVersion);
  }

  revertTo(version: number): DocumentSnapshot | null {
    const entry = this.getByVersion(version);
    return entry?.snapshot ?? null;
  }
}

function computeDiff(from: DocumentSnapshot, to: DocumentSnapshot, fromV: number, toV: number): VersionDiff {
  const changes: VersionDiff['changes'] = [];
  const fromContent = from.content;
  const toContent = to.content;

  let i = 0;
  let j = 0;

  while (i < fromContent.length && j < toContent.length) {
    if (fromContent[i] === toContent[j]) {
      i++;
      j++;
    } else {
      let deletionLen = 0;
      const deletionStart = i;
      while (i < fromContent.length && (i >= toContent.length || fromContent[i] !== toContent[j])) {
        i++;
        deletionLen++;
      }
      let insertionLen = 0;
      const insertionStart = j;
      while (j < toContent.length && (j >= fromContent.length || toContent[j] !== fromContent[i])) {
        j++;
        insertionLen++;
      }
      if (deletionLen > 0) {
        changes.push({ type: 'deletion', position: deletionStart, text: fromContent.slice(deletionStart, i) });
      }
      if (insertionLen > 0) {
        changes.push({ type: 'insertion', position: insertionStart, text: toContent.slice(insertionStart, j) });
      }
    }
  }

  if (i < fromContent.length) {
    changes.push({ type: 'deletion', position: i, text: fromContent.slice(i) });
  }
  if (j < toContent.length) {
    changes.push({ type: 'insertion', position: j, text: toContent.slice(j) });
  }

  return { fromVersion: fromV, toVersion: toV, changes };
}
