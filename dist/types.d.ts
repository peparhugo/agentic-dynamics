import type { Frontmatter } from './frontmatter';
export interface Page {
    slug: string;
    title: string;
    date?: string;
    tags: string[];
    contentHtml: string;
    sourcePath: string;
    outputPath: string;
    template?: string;
    layout?: string;
    data: Frontmatter;
    content?: string;
    html?: string;
}
export interface BuildOptions {
    content: string;
    output: string;
    templates?: string;
    config?: string | false;
}
