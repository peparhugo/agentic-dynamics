import { type PageMetadata } from './parser.js';
export interface PageData {
    slug: string;
    filename: string;
    content: string;
    metadata: PageMetadata;
}
export interface GeneratorOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    layoutsDir?: string;
    partialsDir?: string;
}
export declare function generate(options: GeneratorOptions): Promise<void>;
//# sourceMappingURL=generator.d.ts.map