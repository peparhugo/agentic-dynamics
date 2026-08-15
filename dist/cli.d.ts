#!/usr/bin/env node
import { BuildResult } from './site';
export interface CliOptions {
    command?: string;
    content?: string;
    output?: string;
    templates?: string;
}
export declare function parseArgs(argv: string[]): CliOptions;
export declare function run(argv: string[]): BuildResult;
export declare function main(argv?: string[]): void;
