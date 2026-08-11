export interface Page {
    title: string;
    date: string;
    tags: string[];
    content: string;
    slug: string;
    layout?: string;
    template?: string;
}
export interface BuildOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
    incremental?: boolean;
    clean?: boolean;
}
export interface Plugin {
    name: string;
    onStart?(): void;
    beforeBuild?(options: BuildOptions): void;
    afterBuild?(options: BuildOptions): void;
    onFile?(page: Page): Page;
    onEnd?(): void;
}
export declare function loadPluginsFromConfig(): Plugin[];
//# sourceMappingURL=plugin.d.ts.map