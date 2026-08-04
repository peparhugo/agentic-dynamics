import type { EditorOp } from '@/types/editor';

interface QueueEntry {
  id: string;
  op: EditorOp;
  timestamp: number;
  retries: number;
}

const STORAGE_KEY = 'offline_queue_v1';

export class OfflineQueue {
  private queue: QueueEntry[] = [];

  enqueue(id: string, op: EditorOp): void {
    this.queue.push({ id, op, timestamp: Date.now(), retries: 0 });
  }

  remove(id: string): void {
    this.queue = this.queue.filter(e => e.id !== id);
  }

  getAll(): QueueEntry[] {
    return [...this.queue];
  }

  size(): number {
    return this.queue.length;
  }

  clear(): void {
    this.queue = [];
    this.save();
  }

  persist(): void {
    this.save();
  }

  async load(): Promise<void> {
    try {
      const data = localStorage.getItem(STORAGE_KEY);
      if (data) {
        const entries: QueueEntry[] = JSON.parse(data);
        this.queue = entries;
      }
    } catch {
      this.queue = [];
    }
  }

  private save(): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.queue));
    } catch {
      // storage full or unavailable
    }
  }
}
