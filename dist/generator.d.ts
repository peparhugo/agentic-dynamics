import { PageData } from './plugin.js';
import { BuildStats } from './cache.js';
export interface GeneratorOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    layoutsDir?: string;
    partialsDir?: string;
    incremental?: boolean;
    clean?: boolean;
}
export { PageData, BuildStats };
export declare function generate(options: GeneratorOptions): Promise<BuildStats>;
//# sourceMappingURL=generator.d.ts.map