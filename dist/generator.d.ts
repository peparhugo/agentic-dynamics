interface Page {
    title: string;
    date: string;
    tags: string[];
    content: string;
    slug: string;
    layout?: string;
    template?: string;
}
export declare function parseMarkdownFile(filePath: string): Page | null;
export declare function readContentDirectory(contentDir: string): Page[];
export declare function generateSite(contentDir: string, outputDir: string, templatesDir?: string): number;
export {};
//# sourceMappingURL=generator.d.ts.map