import { PageContext } from './templates';
import { Post } from './types';
export declare function escapeHtml(value: string): string;
export declare function renderIndex(posts: Post[]): string;
export declare function renderPage(post: Post): string;
export declare function pageToContext(post: Post): PageContext;
