export interface Frontmatter {
    title: string;
    date?: string;
    tags?: string[];
}
export interface Page {
    frontmatter: Frontmatter;
    content: string;
    html: string;
    slug: string;
    sourcePath: string;
}
