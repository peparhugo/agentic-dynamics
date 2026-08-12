import type { Page } from './parse';
export interface BuildResult {
    pages: Page[];
    filesWritten: string[];
}
export declare function buildSite(contentDir: string, outputDir: string): BuildResult;
