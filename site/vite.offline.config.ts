import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/postcss';
import {fileURLToPath} from 'node:url';
export default defineConfig({
 plugins:[react()],
 resolve:{alias:{'@':fileURLToPath(new URL('.',import.meta.url))}},
 css:{postcss:{plugins:[tailwindcss()]}},
 build:{outDir:'offline-dist',emptyOutDir:true,copyPublicDir:false,lib:{entry:'app/offline-entry.tsx',name:'DayOne',cssFileName:'day-one',formats:['iife'],fileName:()=> 'day-one.js'},rollupOptions:{output:{inlineDynamicImports:true}}}
});
