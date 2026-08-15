import type { Plugin } from '../plugin';
import type { Page } from '../types';
import { TemplateEngine } from '../templates';
export declare class TemplatePlugin implements Plugin {
    readonly name = "template";
    readonly engine: TemplateEngine;
    constructor(templatesDir: string);
    beforeBuild(): Promise<void>;
    renderPage(page: Page): string;
    renderIndex(pages: Page[]): string;
}
