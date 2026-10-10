const katex=require('../../viewer/vendor/katex/dist/katex.min.js');
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',chunk=>input+=chunk);
process.stdin.on('end',()=>{
  try { for(const latex of JSON.parse(input)) katex.renderToString(latex,{throwOnError:true,trust:false,strict:'error',maxExpand:1000,maxSize:20,output:'htmlAndMathml'}); }
  catch(error) { process.stderr.write(error.message);process.exitCode=1; }
});
