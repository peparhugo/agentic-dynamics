import type { Comment, CommentReply, UserRef, CommentOp } from '@/types/comments';
import { v4 as uuid } from 'uuid';

export class CommentManager {
  private comments: Comment[] = [];

  addComment(position: number, text: string, author: UserRef): Comment {
    const comment: Comment = {
      id: uuid(),
      documentVersion: 0,
      position,
      text,
      author,
      replies: [],
      resolved: false,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    this.comments.push(comment);
    return comment;
  }

  addReply(commentId: string, text: string, author: UserRef): CommentReply | null {
    const comment = this.comments.find(c => c.id === commentId);
    if (!comment) return null;

    const reply: CommentReply = {
      id: uuid(),
      text,
      author,
      createdAt: Date.now(),
    };
    comment.replies.push(reply);
    comment.updatedAt = Date.now();
    return reply;
  }

  resolveComment(commentId: string): boolean {
    const comment = this.comments.find(c => c.id === commentId);
    if (!comment) return false;
    comment.resolved = true;
    comment.updatedAt = Date.now();
    return true;
  }

  reopenComment(commentId: string): boolean {
    const comment = this.comments.find(c => c.id === commentId);
    if (!comment) return false;
    comment.resolved = false;
    comment.updatedAt = Date.now();
    return true;
  }

  deleteComment(commentId: string): boolean {
    const idx = this.comments.findIndex(c => c.id === commentId);
    if (idx === -1) return false;
    this.comments.splice(idx, 1);
    return true;
  }

  getAll(): Comment[] {
    return [...this.comments];
  }

  getForPosition(position: number): Comment[] {
    return this.comments.filter(c => c.position === position);
  }

  getUnresolved(): Comment[] {
    return this.comments.filter(c => !c.resolved);
  }

  applyRemoteOp(op: CommentOp): void {
    switch (op.type) {
      case 'add_comment':
        this.comments.push({
          id: op.payload.id || uuid(),
          documentVersion: op.payload.documentVersion || 0,
          position: op.payload.position || 0,
          text: op.payload.text || '',
          author: op.payload.author || { id: '', name: '' },
          replies: [],
          resolved: false,
          createdAt: Date.now(),
          updatedAt: Date.now(),
        });
        break;
      case 'reply':
        if (op.commentId && op.payload.id) {
          const c = this.comments.find(x => x.id === op.commentId);
          if (c) {
            c.replies.push({
              id: op.payload.id,
              text: op.payload.text || '',
              author: op.payload.author || { id: '', name: '' },
              createdAt: Date.now(),
            });
            c.updatedAt = Date.now();
          }
        }
        break;
      case 'resolve':
        if (op.commentId) this.resolveComment(op.commentId);
        break;
      case 'delete':
        if (op.commentId) this.deleteComment(op.commentId);
        break;
    }
  }
}
