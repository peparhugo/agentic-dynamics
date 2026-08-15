export interface PageMetadata {
    title?: string;
    date?: string;
    tags?: string[];
    template?: string;
    layout?: string;
    [key: string]: string | string[] | undefined;
}
export interface ParsedPage {
    content: string;
    metadata: PageMetadata;
}
export declare function parseMarkdown(content: string): Promise<ParsedPage>;
export declare function parseMarkdownWithYaml(content: string): Promise<ParsedPage>;
//# sourceMappingURL=parser.d.ts.map