export interface ServeOptions {
    contentDir: string;
    outputDir: string;
    port?: number;
    templatesDir?: string;
    layoutsDir?: string;
    partialsDir?: string;
}
export interface ServeResult {
    close: () => Promise<void>;
}
export declare function serve(options: ServeOptions, test?: boolean): Promise<ServeResult>;
//# sourceMappingURL=serve.d.ts.map