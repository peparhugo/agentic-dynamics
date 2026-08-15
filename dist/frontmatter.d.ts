export interface Frontmatter {
    title?: string;
    date?: string;
    tags?: string[];
    [key: string]: unknown;
}
export declare function parseFrontmatter(content: string): {
    data: Frontmatter;
    content: string;
};
//# sourceMappingURL=frontmatter.d.ts.map