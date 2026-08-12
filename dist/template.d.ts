import type { Page } from './parse';
export declare function escapeHtml(input: string): string;
export declare function renderPage(page: Page): string;
export declare function renderIndex(pages: Page[]): string;
