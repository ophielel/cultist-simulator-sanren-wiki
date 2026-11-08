from pathlib import Path
import re
p=Path(__file__).resolve().parent.parent/'tools/build_wiki.py'
s=p.read_text(encoding='utf-8')
pattern=r'        self\.wiki\.add\("机制:战争基础",.*?\n\n    def build_all'
m=re.search(pattern,s,re.S)
if not m:
    raise SystemExit('Superseded guide block not found')
p.write_text(s[:m.start()]+'    def build_all'+s[m.end():],encoding='utf-8',newline='\n')
print('Removed superseded tutorial block:',len(m.group()),'characters')
