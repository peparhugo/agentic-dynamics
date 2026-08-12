import fs from 'fs';
import path from 'path';

export default {
  plugins: [
    {
      name: 'marker',
      afterBuild: (ctx: { outputDir: string }): void => {
        fs.writeFileSync(path.join(ctx.outputDir, 'plugin-ran.txt'), 'yes');
      },
    },
  ],
};
