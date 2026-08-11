import { Page } from './types';
import { BuildCache } from './cache';
export interface GenerateStats {
    built: number;
    skipped: number;
}
export declare function generateSite(pages: Page[], outputDir: string, templateDir?: string, cache?: BuildCache, stats?: GenerateStats): void;
//# sourceMappingURL=generator.d.ts.map