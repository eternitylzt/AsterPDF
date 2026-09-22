const path = require('path');
require('esbuild').buildSync({entryPoints:[path.join(__dirname,'entry.cjs')],bundle:true,platform:'neutral',format:'iife',minify:true,outfile:path.join(__dirname,'../../asterpdf/resources/mathjax-svg.js')});
