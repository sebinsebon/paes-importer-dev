const validator=require('../../viewer/validator.js');
let input='';process.stdin.setEncoding('utf8');process.stdin.on('data',chunk=>input+=chunk);
process.stdin.on('end',()=>{
 try {validator.validateFinal(JSON.parse(input));}
 catch(error){process.stderr.write(error.message);process.exitCode=1;}
});
