export interface Frontmatter {
    title: string;
    date: string;
    tags?: string[];
    template?: string;
    layout?: string;
}
export interface Page {
    frontmatter: Frontmatter;
    html: string;
    slug: string;
}
//# sourceMappingURL=types.d.ts.map