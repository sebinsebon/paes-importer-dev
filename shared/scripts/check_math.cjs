const katex = require('../../viewer/vendor/katex/dist/katex.min.js');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  try {
    for (const entry of JSON.parse(input)) {
      const item = typeof entry === 'string' ? {latex: entry, display: false} : entry;
      if (!item || typeof item.latex !== 'string' || typeof item.display !== 'boolean') throw new Error('Invalid math validation input');
      try {
        katex.renderToString(item.latex, {displayMode: item.display, throwOnError: true, trust: false,
          strict: 'error', maxExpand: 1000, maxSize: 20, output: 'htmlAndMathml'});
      } catch (error) { throw new Error((item.path || 'math') + ': ' + error.message); }
    }
  } catch (error) { process.stderr.write(error.message); process.exitCode = 1; }
});
