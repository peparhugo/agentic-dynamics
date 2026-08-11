import { Page } from '../src/types';
import { Plugin, BuildContext } from '../src/plugin';
export declare class TemplatePlugin implements Plugin {
    name: string;
    private context;
    setContext(context: BuildContext): void;
    afterBuild(pages: Page[]): void;
}
//# sourceMappingURL=template-plugin.d.ts.map