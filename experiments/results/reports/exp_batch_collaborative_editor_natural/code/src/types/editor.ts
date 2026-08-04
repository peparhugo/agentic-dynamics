export interface CharInsert {
  type: 'insert';
  position: number;
  char: string;
  attributes: FormatAttrs;
  clientId: string;
  clock: number;
}

export interface CharDelete {
  type: 'delete';
  position: number;
  length: number;
  clientId: string;
  clock: number;
}

export interface FormatApply {
  type: 'format';
  start: number;
  end: number;
  attributes: FormatAttrs;
  clientId: string;
  clock: number;
}

export type EditorOp = CharInsert | CharDelete | FormatApply;

export interface FormatAttrs {
  bold?: boolean;
  italic?: boolean;
  underline?: boolean;
  strikethrough?: boolean;
  heading?: 'h1' | 'h2' | 'h3';
  color?: string;
  bgColor?: string;
  link?: string;
}

export interface DocumentSnapshot {
  version: number;
  content: string;
  attributes: FormatRange[];
  timestamp: number;
  author: string;
  message?: string;
}

export interface FormatRange {
  start: number;
  end: number;
  attributes: FormatAttrs;
}

export interface DocumentState {
  content: string;
  formats: FormatRange[];
  version: number;
  versionVector: Record<string, number>;
}
