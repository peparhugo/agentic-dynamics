export type ConnectionState = 'connected' | 'connecting' | 'disconnected' | 'reconnecting';

export interface SyncStatus {
  state: ConnectionState;
  pendingOps: number;
  lastSyncAt: number | null;
  peers: number;
  error: string | null;
}

export interface PendingOp {
  id: string;
  op: any;
  timestamp: number;
  retries: number;
}

export interface StateSyncMessage {
  type: 'state_sync';
  documentVersion: number;
  content: string;
  versionVector: Record<string, number>;
}

export interface OpBatchMessage {
  type: 'op_batch';
  ops: any[];
  serverVersion: number;
}

export interface CursorMessage {
  type: 'cursor';
  clientId: string;
  position: number;
  selection?: { anchor: number; head: number };
  user: { id: string; name: string; color: string };
}

export interface AckMessage {
  type: 'ack';
  opIds: string[];
  serverVersion: number;
}

export type WSMessage = StateSyncMessage | OpBatchMessage | CursorMessage | AckMessage;
