#!/usr/bin/env node
export interface CliOptions {
    contentDir: string;
    outputDir: string;
}
export interface ParseArgsResult {
    command?: string;
    options: CliOptions;
    error?: string;
}
export declare function parseArgs(args: string[]): ParseArgsResult;
export declare function run(args: string[]): void;
