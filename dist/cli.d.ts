export interface CliArgs {
    command: string;
    contentDir: string;
    outputDir: string;
    port?: number;
    incremental?: boolean;
    clean?: boolean;
}
export declare function parseArgs(argv: string[]): CliArgs;
//# sourceMappingURL=cli.d.ts.map