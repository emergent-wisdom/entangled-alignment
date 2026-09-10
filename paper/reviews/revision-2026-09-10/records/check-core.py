from pathlib import Path
from collections import Counter
import re, json, difflib, hashlib

p=Path('/Users/parcel/Documents/Code/Emergent Wisdom/entangled-alignment/paper/reviews/revision-2026-09-10/records')
a=(p/'core-before.tex').read_text()
b=(p/'core-after.tex').read_text()
checks={}
heads=lambda s:re.findall(r'\\(?:section|subsection|subsubsection)\*?\{[^\n]*',s)
paragraph_heads=lambda s:re.findall(r'\\paragraph\{([^}]+)\}',s)
labels=lambda s:re.findall(r'\\label\{([^}]+)\}',s)
cites=lambda s:Counter(k.strip() for group in re.findall(r'\\cite[a-zA-Z*]*\{([^}]+)\}',s) for k in group.split(','))
checks['headings_same_order']=heads(a)==heads(b)
checks['named_paragraph_headings_same_order']=paragraph_heads(a)==paragraph_heads(b)
checks['labels_same_order']=labels(a)==labels(b)
checks['citation_occurrences_identical']=cites(a)==cites(b)
checks['environments_identical_counts']=Counter(re.findall(r'\\(?:begin|end)\{([^}]+)\}',a))==Counter(re.findall(r'\\(?:begin|end)\{([^}]+)\}',b))
core_start=a.index('The candidate Reader Core is:')
core_end=a.index('The same seven sentences',core_start)
checks['exact_core_block_and_glossary_once']=b.count(a[core_start:core_end])==1
checks['original_display_math_retained']=all(x in b for x in re.findall(r'\\begin\{equation\}.*?\\end\{equation\}',a,re.S))
full=Path('/private/tmp/ea-review-2026-09-10/source.tex').read_text()
checks['no_unknown_references']=not(set(re.findall(r'\\ref\{([^}]+)\}',b))-set(labels(full)))
normalized=' '.join(b.split())
for k in ['cogito','Borrowed Mortality','Self-Preservation Paradox','Epistemic Grace','Cognitive Buffer Zone','gymnasium for judgment','Bridge Protocol','Deterministic Window Coverage','Total Saturation','Refraction','kernel-saturation','Alignment Checksum','habitable-substrate','cybernetic throttling','historical pattern','It is not a cage---it is a home.']:
    checks['retained_'+k]=k in normalized
nums=lambda s:Counter(re.findall(r'(?<![A-Za-z])\d+(?![A-Za-z])',re.sub(r'\\(?:cite\w*|label|ref)\{[^}]+\}','',s)))
checks['all_original_numeric_occurrences_retained']=not(nums(a)-nums(b))
stack=[]
mismatches=[]
for m in re.finditer(r'\\(begin|end)\{([^}]+)\}',b):
    if m[1]=='begin':stack.append(m[2])
    elif not stack or stack.pop()!=m[2]:mismatches.append(m.group(0))
checks['environment_nesting_balanced']=not stack and not mismatches
plain=re.sub(r'(?m)(?<!\\)%.*','',b)
count=0
underflow=False
for m in re.finditer(r'(?<!\\)[{}]',plain):
    count+=1 if m.group(0)=='{' else -1
    underflow|=count<0
checks['braces_balanced']=count==0 and not underflow
checks['math_delimiters_balanced']=len(re.findall(r'(?<!\\)\$',b))%2==0
for key,start,end in [
    ('positive_welfare_and_ontology_passages_unchanged','Experiential words are attractive because','The long-run target'),
    ('ledger_analogy_unchanged','The most useful mechanism-design analogy','Saturation alone is especially likely to fail.'),
    ('alignment_checksum_unchanged','In this bounded sense the Core can function','Tests~3--5 and the erosion'),
    ('clause_table_and_cogito_unchanged',r'\begin{longtable}',r'\subsection{Self-Stabilization'),
]:
    chunk=a[a.index(start):a.index(end,a.index(start))]
    checks[key]=chunk in b
report={
    'checks':checks,
    'headings':len(heads(b)),
    'named_paragraph_headings':len(paragraph_heads(b)),
    'labels':len(labels(b)),
    'citation_occurrences':sum(cites(b).values()),
    'words_before':len(a.split()),
    'words_after':len(b.split()),
    'sha256_before':hashlib.sha256(a.encode()).hexdigest(),
    'sha256_after':hashlib.sha256(b.encode()).hexdigest(),
}
(p/'core-preservation-checks.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
(p/'core.diff').write_text(''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='core-before.tex',tofile='core-after.tex')))
print(json.dumps(report,indent=2,ensure_ascii=False))
assert all(checks.values())
