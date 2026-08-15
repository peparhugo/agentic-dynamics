import type { Page } from './types';
import { TemplateEngine } from './templates';
export declare function renderPage(page: Page, engine?: TemplateEngine): string;
export declare function renderIndex(pages: Page[], engine?: TemplateEngine): string;
