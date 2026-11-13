"""Validate explicit column plotting without discarding repeated coordinates."""

from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node is needed for browser chart options')
def test_manual_options_preserve_duplicate_rows_calendar_axes_and_nulls():
    """Use scatter for repeated X, preserve missing Y, and handle one-point output."""
    source = Path(__file__).parents[1] / 'ckanext/episerve_theme/fanstatic/forecast_preview.js'
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync(process.argv[1], 'utf8').replace('}());','window.manualOptions = manualOptions;}());');
const context = {window:{}, document:{readyState:'complete',getElementById:()=>null}};
vm.runInNewContext(source, context);
const options = context.window.manualOptions;
const file = {prediction:false, data:{
  columns:[{name:'day',numeric:false,duplicate:true},{name:'value',numeric:true,duplicate:false},{name:'region',numeric:false,duplicate:true}],
  rows:[['2026-01-01',10,'Berlin'],['2026-01-01',20,'Hamburg'],['2026-01-02',null,'Berlin']],row_numbers:[1,4,10],total:10,sampled:true}};
let prepared=options(file,0,1);
assert.equal(prepared.options.chart.type,'scatter');
assert.equal(prepared.options.series[0].data.length,3);
assert.equal(prepared.options.series[0].data[0].x,prepared.options.series[0].data[1].x);
assert.equal(prepared.options.series[0].data[0].y,10);
assert.equal(prepared.options.series[0].data[1].y,20);
assert.equal(prepared.options.series[0].data[2].y,null);
assert.equal(prepared.options.xaxis.title.text,'day');
assert.equal(prepared.options.yaxis.title.text,'value');
assert.equal(prepared.options.xaxis.type,'datetime');
assert.equal(options(file,0,2),null);
prepared=options(file,2,1);
assert.equal(prepared.options.xaxis.type,'numeric'); // Explicit categorical coordinates.
assert.equal(prepared.options.chart.type,'scatter');
const single={prediction:true,data:{columns:[{name:'week',duplicate:false},{name:'infections',numeric:true}],rows:[['2026-W01',0]],row_numbers:[1]}};
prepared=options(single,0,1);
assert.equal(prepared.options.series[0].data.length,1);
assert.equal(prepared.options.series[0].data[0].y,0);
assert(prepared.options.xaxis.min < prepared.options.xaxis.max);
assert.equal(prepared.options.colors[0],'#c62828');
let reset;
prepared.options.chart.toolbar.tools.customIcons[0].click({updateOptions:value=>{reset=value;}});
assert(reset.xaxis.min < reset.xaxis.max);
'''
    subprocess.run(['node', '-e', script, str(source)], check=True, capture_output=True, text=True)
