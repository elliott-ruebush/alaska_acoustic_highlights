// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  site: 'https://mertensia.github.io',
  base: '/alaska_acoustic_highlights',
  compressHTML: true,
  build: {
    inlineStylesheets: 'never',
  },
});
