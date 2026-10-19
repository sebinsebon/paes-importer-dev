"""Synthetic regression for safe nested DOM rendering; no private exam data."""
import subprocess
import unittest
from pathlib import Path

from support import RUNTIME_ROOT as ROOT, DEV_ROOT, WORK_ROOT

class BlockRendererTests(unittest.TestCase):
    def test_nested_blocks_and_math_mode(self):
        script = r"""
const assert=require('node:assert/strict');const R=require('./viewer/block-renderer.js');
class Element{constructor(tag){this.tag=tag;this.children=[];this.style={};this.attrs={};this.classList={add:()=>{}};}append(...items){this.children.push(...items);}replaceChildren(...items){this.children=items;}setAttribute(k,v){this.attrs[k]=v;}}
const doc={createElement:tag=>new Element(tag),createDocumentFragment:()=>new Element('fragment')};
const container=new Element('main');container.ownerDocument=doc;const calls=[];
R.renderBlocks(container,[{type:'text',text:'<script>unsafe()</script>'},{type:'math',latex:'x=1',display:true},{type:'table',rows:[[[{type:'math',latex:'y',display:false}],[{type:'text',text:'cell'}]]]},{type:'image',asset_id:'figure',alt:'Synthetic figure'},{type:'unresolved',reason:'Source pending'}],{assetUrls:new Map([['figure','blob:synthetic']]),katex:{render:(latex,el,config)=>calls.push({latex,config})}});
const blocks=container.children[0].children;assert.equal(blocks[0].textContent,'<script>unsafe()</script>');assert.equal(blocks[0].children.length,0);assert.equal(calls[0].config.displayMode,true);assert.equal(calls[1].config.displayMode,false);assert.equal(calls[0].config.trust,false);assert.equal(blocks[2].children[0].children[0].children[0].children.length,2);assert.equal(blocks[3].children[0].alt,'Synthetic figure');assert.equal(blocks[4].attrs.role,'status');
R.renderBlocks(container,[{type:'math',latex:'bad',display:false}],{katex:{render:()=>{throw Error('bad math')}}});assert.equal(container.children[0].children[0].attrs.role,'alert');
R.renderBlocks(container,[{type:'image',asset_id:'missing',alt:''}]);assert.match(container.children[0].children[0].textContent,/no disponible/);
R.renderBlocks(container,[{type:'text',text:'Un párrafo con '},{type:'math',latex:'x_1^2',display:false},{type:'text',text:' y una fracción.\n\nOtro párrafo.'},{type:'math',latex:'\\frac{1}{2}',display:true}],{katex:{render:()=>{}}});
const mixed=container.children[0].children;assert.equal(mixed[1].tag,'span');assert.equal(mixed[1].style.display,'inline-block');assert.equal(mixed[3].tag,'div');assert.equal(mixed[3].style.display,'block');assert.equal(mixed[2].textContent,' y una fracción.\n\nOtro párrafo.');assert.equal(mixed[2].style.whiteSpace,'pre-wrap');
"""
        result = subprocess.run(["node", "-e", script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

if __name__ == "__main__":
    unittest.main()
