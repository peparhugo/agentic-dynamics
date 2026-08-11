import { Plugin } from './plugin';
export declare class SsgEngine {
    private plugins;
    constructor(additionalPlugins?: Plugin[]);
    build(contentDir: string, outputDir: string, templatesDir?: string): void;
}
//# sourceMappingURL=engine.d.ts.map