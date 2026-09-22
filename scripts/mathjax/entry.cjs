const {mathjax} = require('mathjax-full/js/mathjax.js');
const {TeX} = require('mathjax-full/js/input/tex.js');
const {SVG} = require('mathjax-full/js/output/svg.js');
const {liteAdaptor} = require('mathjax-full/js/adaptors/liteAdaptor.js');
const {RegisterHTMLHandler} = require('mathjax-full/js/handlers/html.js');
require('mathjax-full/js/input/tex/ams/AmsConfiguration.js');
require('mathjax-full/js/input/tex/newcommand/NewcommandConfiguration.js');
const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
globalThis.asterMath = (text, display) => {
  const input = new TeX({packages:['base','ams','newcommand'], maxBuffer:16384, maxMacros:1000,
    formatError:(jax,error)=>{throw Error(error.message);}});
  const document = mathjax.document('', {InputJax:input,OutputJax:new SVG({fontCache:'none'})});
  const node = document.convert(text,{display,em:16,ex:8,containerWidth:640});
  return adaptor.outerHTML(adaptor.firstChild(node));
};
