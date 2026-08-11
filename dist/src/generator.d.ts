import { Page } from './types';
import { TemplateEngine } from './templates';
export declare function generatePageHtml(page: Page, engine?: TemplateEngine): string;
export declare function generateIndexHtml(pages: Page[], engine?: TemplateEngine): string;
