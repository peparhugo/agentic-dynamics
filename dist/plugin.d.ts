import { Page, SSGOptions } from './types';
export interface BuildContext {
    options: SSGOptions;
    pages: Page[];
    outputDir: string;
    templateDir?: string;
    [key: string]: any;
}
export interface Plugin {
    name: string;
    onStart?(context: BuildContext): void | Promise<void>;
    beforeBuild?(context: BuildContext): void | Promise<void>;
    onFile?(page: Page, context: BuildContext): void | Promise<void>;
    afterBuild?(context: BuildContext): void | Promise<void>;
    onEnd?(context: BuildContext): void | Promise<void>;
}
export interface SSGConfig {
    plugins?: (string | {
        name: string;
        options?: Record<string, any>;
    })[];
}
//# sourceMappingURL=plugin.d.ts.map