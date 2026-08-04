import type { CursorPosition, UserInfo } from '@/types/presence';

const CURSOR_TIMEOUT_MS = 30_000;

export class CursorManager {
  private cursors: Map<string, CursorPosition> = new Map();
  private cleanupInterval: ReturnType<typeof setInterval> | null = null;

  start(): void {
    this.cleanupInterval = setInterval(() => this.cleanupStale(), 5000);
  }

  stop(): void {
    if (this.cleanupInterval) {
      clearInterval(this.cleanupInterval);
      this.cleanupInterval = null;
    }
  }

  updateCursor(cursor: CursorPosition): void {
    cursor.lastUpdated = Date.now();
    this.cursors.set(cursor.clientId, cursor);
  }

  removeCursor(clientId: string): void {
    this.cursors.delete(clientId);
  }

  getAllCursors(): CursorPosition[] {
    return Array.from(this.cursors.values())
      .filter(c => Date.now() - c.lastUpdated < CURSOR_TIMEOUT_MS);
  }

  getCursorPosition(clientId: string): CursorPosition | undefined {
    return this.cursors.get(clientId);
  }

  private cleanupStale(): void {
    const now = Date.now();
    for (const [clientId, cursor] of this.cursors) {
      if (now - cursor.lastUpdated > CURSOR_TIMEOUT_MS) {
        this.cursors.delete(clientId);
      }
    }
  }
}
