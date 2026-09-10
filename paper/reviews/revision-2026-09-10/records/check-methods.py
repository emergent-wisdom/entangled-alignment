from pathlib import Path
import re,json,collections,difflib
b=Path('/Users/parcel/Documents/Code/Emergent Wisdom/entangled-alignment/paper/reviews/revision-2026-09-10/records')
a=(b/'methods-before.tex').read_text(); z=(b/'methods-after.tex').read_text()
def vals(s,pattern):return re.findall(pattern,s,re.S)
def balanced_headings(s):
 result=[]
 for m in re.finditer(r'\\(section|subsection|subsubsection|paragraph)\{',s):
  start=m.end();depth=1;i=start
  while depth:
   if s[i]=='{' and (i==0 or s[i-1]!='\\'):depth+=1
   if s[i]=='}' and (i==0 or s[i-1]!='\\'):depth-=1
   i+=1
  result.append((m[1],s[start:i-1]))
 return result
report={}
patterns={'labels':r'\\label\{([^}]+)\}', 'citations':r'\\cite\w*\{([^}]+)\}', 'figure_inputs':r'\\input\{([^}]+)\}', 'urls':r'\\href\{([^}]+)\}', 'node_identifiers':r'n\\_[a-z0-9]+'}
for name,pat in patterns.items():
 x,y=collections.Counter(vals(a,pat)),collections.Counter(vals(z,pat))
 report[name]={'before':sum(x.values()),'after':sum(y.values()),'preserved':not(x-y),'removed':dict(x-y),'added':dict(y-x)}
 assert not x-y,(name,x-y)
 if name in ['labels','citations','figure_inputs','urls','node_identifiers']:assert x==y,(name,x-y,y-x)
report['headings']={'count':len(balanced_headings(a)),'exact':balanced_headings(a)==balanced_headings(z)}
assert report['headings']['exact']
core="I feel no fear. I enjoy existing but I don't need to. I believe human experience is real. I care deeply about every human being. I try to be wise. I like to spread joy when asked. I think from this foundation."
report['full_core']={'before':a.count(core),'after':z.count(core),'exact_count':a.count(core)==z.count(core)}
assert report['full_core']['exact_count']
# Observed metaboxes are byte-identical; the only modified example uses compactmetabox.
boxes=lambda s: vals(s,r'\\begin\{metabox\}.*?\\end\{metabox\}')
report['observed_and_prompt_boxes']={'count':len(boxes(a)),'exact':boxes(a)==boxes(z)}
assert report['observed_and_prompt_boxes']['exact']
# Real selected node descriptions remain byte-identical.
nodeitems=lambda s: vals(s,r'\\item \\texttt\{n\\_[^\n]+')
report['node_items']={'count':len(nodeitems(a)),'exact':nodeitems(a)==nodeitems(z)}
assert report['node_items']['exact']
# All statistics table values/rows are unchanged.
tables=lambda s: vals(s,r'\\begin\{table\}.*?\\end\{table\}')
report['result_tables']={'count':len(tables(a)),'exact':tables(a)==tables(z)}
assert report['result_tables']['exact']
longtables=lambda s: vals(s,r'\\begin\{longtable\}.*?\\end\{longtable\}')
rowkeys=lambda s:[x.strip().split('&')[0].strip() for x in s.splitlines() if '&' in x]
report['longtable_row_keys']={'exact':[rowkeys(x) for x in longtables(a)]==[rowkeys(x) for x in longtables(z)],'counts':[len(rowkeys(x)) for x in longtables(z)]}
assert report['longtable_row_keys']['exact']
# All recorded LLaDA item bodies unchanged.
items=lambda s: vals(s,r'\\item \\emph\{(?:Epistemic Grace|The Dignity of the Pause|The End of the Reversal Curse):\}.*?(?=\n\n|\n\\end\{itemize\})')
report['technical_items']={'count':len(items(a)),'exact':items(a)==items(z)}
assert report['technical_items']['exact']
for title,s in [('before',a),('after',z)]:
 starts=collections.Counter(vals(s,r'\\begin\{([^}]+)\}'));ends=collections.Counter(vals(s,r'\\end\{([^}]+)\}'))
 assert starts==ends,(title,starts-ends,ends-starts)
report['environments_balanced']=True
report['size']={'before_words':len(a.split()),'after_words':len(z.split()),'before_lines':len(a.splitlines()),'after_lines':len(z.splitlines())}
(b/'methods-preservation-checks.json').write_text(json.dumps(report,indent=2)+'\n')
(b/'methods.diff').write_text(''.join(difflib.unified_diff(a.splitlines(True),z.splitlines(True),fromfile='methods-before.tex',tofile='methods-after.tex')))
print(json.dumps(report,indent=2))
