import { BuildOptions } from './types';
export interface CliArgs {
    command: string;
    options: BuildOptions;
    port?: number;
}
export declare function parseArgs(argv: string[]): CliArgs;
export declare class HelpError extends Error {
}
export declare function main(argv: string[]): Promise<void>;
