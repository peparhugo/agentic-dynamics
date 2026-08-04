import { create } from 'zustand';
import type { Comment } from '@/types/comments';
import type { UserRef } from '@/types/comments';
import { CommentManager } from '@/services/CommentManager';

interface CommentStore {
  commentManager: CommentManager;
  comments: Comment[];
  showResolved: boolean;

  addComment: (position: number, text: string, author: UserRef) => Comment;
  addReply: (commentId: string, text: string, author: UserRef) => void;
  resolveComment: (commentId: string) => void;
  reopenComment: (commentId: string) => void;
  deleteComment: (commentId: string) => void;
  toggleShowResolved: () => void;
  getCommentsAtPosition: (position: number) => Comment[];
  refresh: () => void;
}

export const useCommentStore = create<CommentStore>((set, get) => ({
  commentManager: new CommentManager(),
  comments: [],
  showResolved: false,

  addComment: (position, text, author) => {
    const comment = get().commentManager.addComment(position, text, author);
    set({ comments: get().commentManager.getAll() });
    return comment;
  },
  addReply: (commentId, text, author) => {
    get().commentManager.addReply(commentId, text, author);
    set({ comments: get().commentManager.getAll() });
  },
  resolveComment: (commentId) => {
    get().commentManager.resolveComment(commentId);
    set({ comments: get().commentManager.getAll() });
  },
  reopenComment: (commentId) => {
    get().commentManager.reopenComment(commentId);
    set({ comments: get().commentManager.getAll() });
  },
  deleteComment: (commentId) => {
    get().commentManager.deleteComment(commentId);
    set({ comments: get().commentManager.getAll() });
  },
  toggleShowResolved: () => set((s) => ({ showResolved: !s.showResolved })),
  getCommentsAtPosition: (position) => get().commentManager.getForPosition(position),
  refresh: () => set({ comments: get().commentManager.getAll() }),
}));
