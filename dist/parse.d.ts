export interface Page {
    slug: string;
    title: string;
    date?: string;
    tags: string[];
    contentHtml: string;
    source: string;
}
export declare function slugify(filename: string): string;
export declare function parseMarkdown(content: string, source: string): Page;
export declare function readMarkdownFile(filePath: string): Page;
