export interface Comment {
  id: string;
  documentVersion: number;
  position: number;
  text: string;
  author: UserRef;
  replies: CommentReply[];
  resolved: boolean;
  createdAt: number;
  updatedAt: number;
}

export interface CommentReply {
  id: string;
  text: string;
  author: UserRef;
  createdAt: number;
}

export interface UserRef {
  id: string;
  name: string;
}

export interface CommentOp {
  type: 'add_comment' | 'reply' | 'resolve' | 'delete';
  commentId?: string;
  payload: Partial<Comment>;
}
