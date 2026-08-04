export type NotificationChannel = 'in-app' | 'push' | 'email';

export type NotificationType = string;

export type NotificationAction = 'reply' | 'approve' | 'dismiss';

export type NotificationStatus = 'read' | 'unread';

export interface ChannelPreferences {
  enabled: boolean;
  types: Record<NotificationType, boolean>;
}

export interface NotificationPreferences {
  channels: Record<NotificationChannel, ChannelPreferences>;
  batching: {
    enabled: boolean;
    windowMs: number;
    maxBatchSize: number;
  };
  quietHours: {
    enabled: boolean;
    start: string;
    end: string;
    timezone: string;
  };
}

export interface NotificationMetadata {
  createdAt: string;
  deliveredAt?: string;
  readAt?: string;
  batchId?: string;
  sourceId?: string;
  url?: string;
  icon?: string;
}

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  body: string;
  status: NotificationStatus;
  channel: NotificationChannel[];
  data?: Record<string, unknown>;
  actions?: NotificationAction[];
  metadata: NotificationMetadata;
}

export interface BatchedNotification {
  id: string;
  notifications: Notification[];
  summary: string;
  count: number;
  windowStart: string;
  windowEnd: string;
  delivered: boolean;
}

export interface WebSocketMessage {
  type: 'notification' | 'read_sync' | 'batch' | 'preference_sync' | 'pong';
  payload: unknown;
  timestamp: string;
}

export interface OfflineAction {
  id: string;
  action: NotificationAction;
  notificationId: string;
  payload?: Record<string, unknown>;
  timestamp: string;
  retries: number;
}

export interface ConnectionState {
  status: 'connected' | 'disconnected' | 'reconnecting';
  lastConnected?: string;
  retryCount: number;
  maxRetries: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  cursor?: string;
  hasMore: boolean;
}

export const DEFAULT_PREFERENCES: NotificationPreferences = {
  channels: {
    'in-app': {
      enabled: true,
      types: {},
    },
    push: {
      enabled: true,
      types: {},
    },
    email: {
      enabled: true,
      types: {},
    },
  },
  batching: {
    enabled: true,
    windowMs: 300000,
    maxBatchSize: 20,
  },
  quietHours: {
    enabled: false,
    start: '22:00',
    end: '07:00',
    timezone: 'UTC',
  },
};
