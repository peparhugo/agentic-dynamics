export interface Page {
    slug: string;
    title: string;
    date?: string;
    tags: string[];
    content: string;
    html: string;
    sourcePath: string;
}
export interface BuildOptions {
    contentDir: string;
    outputDir: string;
}
export interface ParsedFrontmatter {
    title?: string;
    date?: string;
    tags?: string[];
    [key: string]: unknown;
}
