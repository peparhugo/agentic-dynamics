import { PageData } from './page';
import { PluginManager } from './plugin';
export declare function generatePageHtml(page: PageData, outputDir: string, templateDir?: string, pluginManager?: PluginManager): Promise<void>;
export declare function generateIndexHtml(pages: PageData[], outputDir: string): Promise<void>;
//# sourceMappingURL=generator.d.ts.map