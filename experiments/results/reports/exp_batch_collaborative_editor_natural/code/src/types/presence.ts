export interface CursorPosition {
  clientId: string;
  user: UserInfo;
  position: number;
  selection?: {
    anchor: number;
    head: number;
  };
  lastUpdated: number;
}

export interface UserInfo {
  id: string;
  name: string;
  color: string;
  avatarUrl?: string;
}

export const USER_COLORS = [
  '#e06c75', '#61afef', '#98c379', '#d19a66',
  '#c678dd', '#56b6c2', '#e5c07b', '#be5046',
];
