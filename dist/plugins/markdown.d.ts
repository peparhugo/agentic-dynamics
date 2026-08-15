import type { Plugin } from '../plugin';
import type { Page } from '../types';
export declare class MarkdownPlugin implements Plugin {
    readonly name = "markdown";
    onFile(page: Page): Page;
}
