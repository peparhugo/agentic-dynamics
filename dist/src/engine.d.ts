import { Plugin } from './plugin';
import { BuildOptions } from './build';
export declare class SsgEngine {
    private plugins;
    constructor(additionalPlugins?: Plugin[]);
    build(contentDir: string, outputDir: string, templatesDir?: string, options?: BuildOptions): void;
}
//# sourceMappingURL=engine.d.ts.map