import { Plugin, Page, BuildOptions } from '../plugin';
export declare function parseMarkdownFile(filePath: string): Page | null;
export declare function readContentDirectory(contentDir: string): Page[];
export declare class MarkdownPlugin implements Plugin {
    name: string;
    pages: Page[];
    beforeBuild(options: BuildOptions): void;
    onFile(page: Page): Page;
}
//# sourceMappingURL=markdown.d.ts.map