export interface PageFrontmatter {
    title: string;
    date: string;
    tags: string[];
}
export interface PageData {
    slug: string;
    frontmatter: PageFrontmatter;
    content: string;
    html: string;
}
export interface ParseResult {
    pages: PageData[];
}
export interface ParseOptions {
    contentDir: string;
    outputDir: string;
}
