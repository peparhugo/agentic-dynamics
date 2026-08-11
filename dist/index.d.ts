import { PageData, BuildOptions } from "./types";
export declare function getMarkdownFiles(contentDir: string): Promise<string[]>;
export declare function parseMarkdownFile(contentDir: string, filePath: string): Promise<PageData>;
export declare function generatePageHtml(page: PageData): string;
export declare function generateIndexHtml(pages: PageData[]): string;
export declare function build(options: BuildOptions): Promise<void>;
