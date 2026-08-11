export interface Frontmatter {
    title: string;
    date: string;
    tags: string[];
    template?: string;
    layout?: string;
}
export interface Page {
    slug: string;
    frontmatter: Frontmatter;
    content: string;
    html: string;
}
//# sourceMappingURL=types.d.ts.map