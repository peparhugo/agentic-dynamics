import type { DocumentSnapshot } from './editor';

export interface VersionEntry {
  id: string;
  version: number;
  timestamp: number;
  author: string;
  message: string;
  snapshot: DocumentSnapshot;
  isAutoSave: boolean;
}

export interface VersionDiff {
  fromVersion: number;
  toVersion: number;
  changes: DiffChange[];
}

export type DiffChange =
  | { type: 'insertion'; position: number; text: string }
  | { type: 'deletion'; position: number; text: string }
  | { type: 'format'; start: number; end: number; before: object; after: object };
