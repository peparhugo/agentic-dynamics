import { Frontmatter, PageData } from "./types";
export interface TemplateEngine {
    renderPage(frontmatter: Frontmatter, content: string, template?: string, layout?: string): string;
    renderIndex(pages: PageData[]): string;
}
export declare function createTemplateEngine(templatesDir: string): Promise<TemplateEngine | null>;
