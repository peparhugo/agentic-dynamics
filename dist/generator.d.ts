export interface PageData {
    title: string;
    date: string;
    tags: string[];
    content: string;
    html: string;
    slug: string;
    template?: string;
}
export declare function buildSite(contentDir: string, outputDir: string, templatesDir?: string): void;
//# sourceMappingURL=generator.d.ts.map