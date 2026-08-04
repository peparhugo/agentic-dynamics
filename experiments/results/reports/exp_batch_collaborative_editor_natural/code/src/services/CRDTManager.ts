import type { EditorOp, CharInsert, CharDelete, FormatApply, DocumentState, FormatAttrs, FormatRange } from '@/types/editor';
import { v4 as uuid } from 'uuid';

interface CRDTChar {
  id: string;
  char: string;
  position: number;
  attributes: FormatAttrs;
  clientId: string;
  clock: number;
  isDeleted: boolean;
  lamport: number;
}

export class CRDTManager {
  private chars: CRDTChar[] = [];
  private clientId: string;
  private clock: number = 0;
  private versionVector: Record<string, number> = {};
  private lamportClock: number = 0;

  constructor(clientId?: string) {
    this.clientId = clientId ?? uuid();
  }

  getClientId(): string {
    return this.clientId;
  }

  getClock(): number {
    return this.clock;
  }

  getVersionVector(): Record<string, number> {
    return { ...this.versionVector };
  }

  tick(): number {
    this.clock += 1;
    return this.clock;
  }

  advanceLamport(): number {
    this.lamportClock += 1;
    return this.lamportClock;
  }

  getLamport(): number {
    return this.lamportClock;
  }

  updateLamport(remote: number): void {
    this.lamportClock = Math.max(this.lamportClock, remote) + 1;
  }

  localInsert(position: number, text: string, attributes: FormatAttrs = {}): CharInsert[] {
    const ops: CharInsert[] = [];
    for (let i = 0; i < text.length; i++) {
      const clock = this.tick();
      const char: CRDTChar = {
        id: `${this.clientId}:${clock}`,
        char: text[i],
        position,
        attributes: { ...attributes },
        clientId: this.clientId,
        clock,
        isDeleted: false,
        lamport: this.advanceLamport(),
      };
      this.chars.push(char);
      ops.push({
        type: 'insert',
        position,
        char: text[i],
        attributes: { ...attributes },
        clientId: this.clientId,
        clock,
      });
      position++;
    }
    this.versionVector[this.clientId] = Math.max(this.versionVector[this.clientId] || 0, this.clock);
    return ops;
  }

  localDelete(position: number, length: number): CharDelete[] {
    const ops: CharDelete[] = [];
    if (length > 0) {
      const clock = this.tick();
      ops.push({
        type: 'delete',
        position,
        length,
        clientId: this.clientId,
        clock,
      });
    }
    this.versionVector[this.clientId] = Math.max(this.versionVector[this.clientId] || 0, this.clock);
    return ops;
  }

  localFormat(start: number, end: number, attributes: FormatAttrs): FormatApply[] {
    const ops: FormatApply[] = [];
    const clock = this.tick();
    ops.push({
      type: 'format',
      start,
      end,
      attributes,
      clientId: this.clientId,
      clock,
    });
    this.versionVector[this.clientId] = Math.max(this.versionVector[this.clientId] || 0, this.clock);
    return ops;
  }

  applyRemoteInsert(op: CharInsert): boolean {
    if (op.clientId === this.clientId) return false;

    const existing = this.chars.find(c => c.id === `${op.clientId}:${op.clock}`);
    if (existing) return false;

    const char: CRDTChar = {
      id: `${op.clientId}:${op.clock}`,
      char: op.char,
      position: op.position,
      attributes: { ...op.attributes },
      clientId: op.clientId,
      clock: op.clock,
      isDeleted: false,
      lamport: this.advanceLamport(),
    };
    this.chars.push(char);
    this.versionVector[op.clientId] = Math.max(this.versionVector[op.clientId] || 0, op.clock);
    return true;
  }

  applyRemoteDelete(op: CharDelete): boolean {
    if (op.clientId === this.clientId) return false;
    this.versionVector[op.clientId] = Math.max(this.versionVector[op.clientId] || 0, op.clock);
    return true;
  }

  applyRemoteFormat(op: FormatApply): boolean {
    if (op.clientId === this.clientId) return false;
    this.versionVector[op.clientId] = Math.max(this.versionVector[op.clientId] || 0, op.clock);
    return true;
  }

  getContent(): string {
    const sorted = this.chars
      .filter(c => !c.isDeleted)
      .sort((a, b) => {
        if (a.position !== b.position) return a.position - b.position;
        return a.lamport - b.lamport;
      });

    return sorted.map(c => c.char).join('');
  }

  getFormats(): FormatRange[] {
    const ranges: FormatRange[] = [];
    let current: FormatRange | null = null;

    const sorted = this.chars
      .filter(c => !c.isDeleted)
      .sort((a, b) => a.position - b.position);

    for (let i = 0; i < sorted.length; i++) {
      const attrs = sorted[i].attributes;
      const pos = i;

      if (!current) {
        current = { start: pos, end: pos + 1, attributes: { ...attrs } };
        continue;
      }

      if (areAttrsEqual(current.attributes, attrs)) {
        current.end = pos + 1;
      } else {
        ranges.push(current);
        current = { start: pos, end: pos + 1, attributes: { ...attrs } };
      }
    }

    if (current) {
      ranges.push(current);
    }

    return ranges;
  }

  getState(): DocumentState {
    return {
      content: this.getContent(),
      formats: this.getFormats(),
      version: Object.values(this.versionVector).reduce((a, b) => a + b, 0),
      versionVector: { ...this.versionVector },
    };
  }

  snapshot(): DocumentState {
    return this.getState();
  }

  applyFullState(state: DocumentState): void {
    this.chars = [];
    for (let i = 0; i < state.content.length; i++) {
      this.chars.push({
        id: `restore:${i}`,
        char: state.content[i],
        position: i,
        attributes: this.findFormatAt(i, state.formats),
        clientId: 'system',
        clock: 0,
        isDeleted: false,
        lamport: i,
      });
    }
    this.versionVector = { ...state.versionVector };
  }

  private findFormatAt(pos: number, formats: FormatRange[]): FormatAttrs {
    const attrs: FormatAttrs = {};
    for (const f of formats) {
      if (pos >= f.start && pos < f.end) {
        Object.assign(attrs, f.attributes);
      }
    }
    return attrs;
  }
}

function areAttrsEqual(a: FormatAttrs, b: FormatAttrs): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) {
    if ((a as any)[k] !== (b as any)[k]) return false;
  }
  return true;
}
