import type { EditorOp, DocumentState } from '@/types/editor';
import type { WSMessage, OpBatchMessage, CursorMessage, ConnectionState } from '@/types/sync';
import { CRDTManager } from './CRDTManager';
import { OfflineQueue } from './OfflineQueue';
import { IndexedDBManager } from './IndexedDBManager';

type SyncCallback = (txn: SyncTransaction) => void;

export interface SyncTransaction {
  ops: EditorOp[];
  documentVersion: number;
  cursors: CursorMessage[];
  source: 'local' | 'remote';
}

export class SyncEngine {
  private crdt: CRDTManager;
  private offlineQueue: OfflineQueue;
  private idbManager: IndexedDBManager;
  private ws: WebSocket | null = null;
  private connectionState: ConnectionState = 'disconnected';
  private listeners: Set<SyncCallback> = new Set();
  private peers: number = 0;
  private url: string;
  private pendingAcks: Set<string> = new Set();
  private lastSyncVersion: number = 0;
  private currentUser: { id: string; name: string; color: string };
  private cursorPosition: number = 0;

  constructor(crdt: CRDTManager, url: string, user: { id: string; name: string; color: string }) {
    this.crdt = crdt;
    this.url = url;
    this.currentUser = user;
    this.offlineQueue = new OfflineQueue();
    this.idbManager = new IndexedDBManager('collab-editor');
  }

  async initialize(): Promise<void> {
    await this.idbManager.init();
    const stored = await this.idbManager.loadDocument();
    if (stored) {
      this.crdt.applyFullState(stored);
      this.lastSyncVersion = stored.version;
    }
    await this.flushOfflineQueue();
  }

  connect(): void {
    this.setConnectionState('connecting');
    try {
      this.ws = new WebSocket(this.url);
      this.ws.onopen = () => this.handleOpen();
      this.ws.onmessage = (evt) => this.handleMessage(evt.data);
      this.ws.onclose = () => this.handleClose();
      this.ws.onerror = () => this.handleError();
    } catch {
      this.setConnectionState('disconnected');
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setConnectionState('disconnected');
  }

  onSync(cb: SyncCallback): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  getConnectionState(): ConnectionState {
    return this.connectionState;
  }

  getPeers(): number {
    return this.peers;
  }

  getPendingCount(): number {
    return this.offlineQueue.size();
  }

  setCursorPosition(position: number, selection?: { anchor: number; head: number }): void {
    this.cursorPosition = position;
    this.sendCursor(position, selection);
  }

  private handleOpen(): void {
    this.setConnectionState('connected');
    this.syncState();
    this.flushOfflineQueue();
  }

  private handleMessage(data: string): void {
    try {
      const msg: WSMessage = JSON.parse(data);
      switch (msg.type) {
        case 'state_sync':
          this.handleStateSync(msg);
          break;
        case 'op_batch':
          this.handleOpBatch(msg);
          break;
        case 'cursor':
          this.handleCursor(msg);
          break;
        case 'ack':
          this.handleAck(msg);
          break;
      }
    } catch {
      // ignore malformed messages
    }
  }

  private handleClose(): void {
    this.setConnectionState('disconnected');
    this.scheduleReconnect();
  }

  private handleError(): void {
    this.setConnectionState('disconnected');
  }

  private scheduleReconnect(): void {
    setTimeout(() => {
      if (this.connectionState === 'disconnected') {
        this.setConnectionState('reconnecting');
        this.connect();
      }
    }, 2000 + Math.random() * 3000);
  }

  private handleStateSync(msg: any): void {
    const state: DocumentState = {
      content: msg.content,
      formats: [],
      version: msg.documentVersion,
      versionVector: msg.versionVector,
    };
    if (msg.documentVersion > this.lastSyncVersion) {
      this.crdt.applyFullState(state);
      this.lastSyncVersion = msg.documentVersion;
      this.notifyListeners({ ops: [], documentVersion: msg.documentVersion, cursors: [], source: 'remote' });
    }
  }

  private handleOpBatch(msg: OpBatchMessage): void {
    const remoteOps: EditorOp[] = [];
    for (const op of msg.ops) {
      switch (op.type) {
        case 'insert':
          if (this.crdt.applyRemoteInsert(op)) {
            remoteOps.push(op);
          }
          break;
        case 'delete':
          this.crdt.applyRemoteDelete(op);
          remoteOps.push(op);
          break;
        case 'format':
          this.crdt.applyRemoteFormat(op);
          remoteOps.push(op);
          break;
      }
    }
    this.lastSyncVersion = msg.serverVersion;
    if (remoteOps.length > 0) {
      this.notifyListeners({
        ops: remoteOps,
        documentVersion: msg.serverVersion,
        cursors: [],
        source: 'remote',
      });
    }
  }

  private handleCursor(msg: CursorMessage): void {
    if (msg.clientId !== this.currentUser.id) {
      this.notifyListeners({
        ops: [],
        documentVersion: this.lastSyncVersion,
        cursors: [msg],
        source: 'remote',
      });
    }
  }

  private handleAck(msg: { type: 'ack'; opIds: string[]; serverVersion: number }): void {
    for (const id of msg.opIds) {
      this.pendingAcks.delete(id);
      this.offlineQueue.remove(id);
    }
    this.lastSyncVersion = msg.serverVersion;
  }

  sendOps(ops: EditorOp[]): void {
    const batched: string[] = [];
    for (const op of ops) {
      const id = `${op.clientId}:${op.clock}`;
      batched.push(id);
      this.pendingAcks.add(id);
      this.offlineQueue.enqueue(id, op);
    }

    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'op_batch',
        ops,
        clientId: this.crdt.getClientId(),
      }));
    } else {
      this.offlineQueue.persist();
    }
  }

  private sendCursor(position: number, selection?: { anchor: number; head: number }): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'cursor',
        clientId: this.currentUser.id,
        position,
        selection,
        user: this.currentUser,
      }));
    }
  }

  private syncState(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'request_sync',
        lastVersion: this.lastSyncVersion,
      }));
    }
  }

  private async flushOfflineQueue(): Promise<void> {
    const pending = this.offlineQueue.getAll();
    if (pending.length > 0 && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'op_batch',
        ops: pending.map(p => p.op),
        clientId: this.crdt.getClientId(),
      }));
      this.offlineQueue.clear();
    }
  }

  private setConnectionState(state: ConnectionState): void {
    this.connectionState = state;
  }

  private notifyListeners(txn: SyncTransaction): void {
    for (const listener of this.listeners) {
      try {
        listener(txn);
      } catch {
        // isolate listener failures
      }
    }
  }

  async persistDocument(): Promise<void> {
    const state = this.crdt.getState();
    await this.idbManager.saveDocument(state);
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setConnectionState('disconnected');
  }
}
