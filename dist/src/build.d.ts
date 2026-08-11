export interface BuildOptions {
    contentDir: string;
    outputDir: string;
    templatesDir?: string;
}
export declare function build(options: BuildOptions): void;
