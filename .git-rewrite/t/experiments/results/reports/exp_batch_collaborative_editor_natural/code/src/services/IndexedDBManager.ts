import { openDB, type IDBPDatabase } from 'idb';
import type { DocumentState } from '@/types/editor';

const DB_VERSION = 1;
const DOC_STORE = 'documents';
const VERSION_STORE = 'versions';

interface StoredDocument {
  id: string;
  state: DocumentState;
  updatedAt: number;
}

interface StoredVersion {
  id: string;
  version: number;
  snapshot: string;
  timestamp: number;
  author: string;
  message: string;
}

export class IndexedDBManager {
  private db: IDBPDatabase | null = null;
  private dbName: string;

  constructor(dbName: string) {
    this.dbName = dbName;
  }

  async init(): Promise<void> {
    this.db = await openDB(this.dbName, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(DOC_STORE)) {
          db.createObjectStore(DOC_STORE, { keyPath: 'id' });
        }
        if (!db.objectStoreNames.contains(VERSION_STORE)) {
          const store = db.createObjectStore(VERSION_STORE, { keyPath: 'id' });
          store.createIndex('version', 'version', { unique: false });
        }
      },
    });
  }

  async saveDocument(state: DocumentState): Promise<void> {
    if (!this.db) return;
    const doc: StoredDocument = {
      id: 'current',
      state,
      updatedAt: Date.now(),
    };
    await this.db.put(DOC_STORE, doc);
  }

  async loadDocument(): Promise<DocumentState | null> {
    if (!this.db) return null;
    const doc = await this.db.get(DOC_STORE, 'current') as StoredDocument | undefined;
    return doc?.state ?? null;
  }

  async saveVersion(version: StoredVersion): Promise<void> {
    if (!this.db) return;
    await this.db.put(VERSION_STORE, version);
  }

  async getVersions(): Promise<StoredVersion[]> {
    if (!this.db) return [];
    return this.db.getAllFromIndex(VERSION_STORE, 'version');
  }

  async getVersion(versionId: string): Promise<StoredVersion | null> {
    if (!this.db) return null;
    return (await this.db.get(VERSION_STORE, versionId)) as StoredVersion | undefined ?? null;
  }
}
