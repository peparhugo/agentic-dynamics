import { PageData } from './plugin.js';
export interface GeneratorOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    layoutsDir?: string;
    partialsDir?: string;
}
export { PageData };
export declare function generate(options: GeneratorOptions): Promise<void>;
//# sourceMappingURL=generator.d.ts.map