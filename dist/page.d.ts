export interface PageData {
    title: string;
    date?: string;
    tags?: string[];
    html: string;
    slug: string;
    template?: string;
    layout?: string;
    [key: string]: unknown;
}
export declare function processMarkdownFile(filename: string, content: string): Promise<PageData>;
//# sourceMappingURL=page.d.ts.map