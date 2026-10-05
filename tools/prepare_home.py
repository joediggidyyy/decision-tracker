"""Prepare a scoped home edit and a sanitized browser proof copy."""
from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parents[1]
import argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--home",required=True)
home=Path(parser.parse_args().home).resolve()
raw=home.read_bytes();text=raw.decode("utf-8")
section=next(m.group() for m in re.finditer(r'<section[^>]*>[\s\S]*?</section>',text) if "Sites and tools" in m.group())
ledger=next(m.group() for m in re.finditer(r'<a\b[^>]*>[\s\S]*?</a>',section) if 'id="ledger-pending"' in m.group())
tracker='<a class="card" href="http://127.0.0.1:8765/" target="_blank" rel="noopener noreferrer"><span class="card__kind">Application</span><span class="card__title">Decision Tracker</span><span class="card__description">Project decisions, evidence and history. Local service required.</span><span class="card__action">Open tracker</span></a>'
tools='<section class="home-section" aria-labelledby="tools-heading"><div class="home-section__heading"><h2 id="tools-heading">Tools</h2></div><div class="cards cards--connected">\n        '+tracker+'\n        '+ledger+'\n      </div></section>\n      '
marker='<section class="home-section" aria-labelledby="workspace-heading">'
replacement=section.replace("Sites and tools","Sites").replace(ledger,"")
proposed=text.replace(section,replacement).replace(marker,tools+marker)
out=root/".local/home-integration";out.mkdir(parents=True,exist_ok=True)
receipt={"source_sha256":hashlib.sha256(raw).hexdigest(),"prior_section":section,"replacement_section":replacement,"insertion_marker":marker,"inserted_section":tools,"proposed_sha256":hashlib.sha256(proposed.encode()).hexdigest()}
(out/"scoped-change.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
# Never retain or serve the private folder index or credential-bearing launch links.
preview=re.sub(r'<script\b[^>]*>[\s\S]*?</script>',"",proposed)
preview=re.sub(r'href="([^"]*)"',lambda m:m.group() if m[1].startswith(("https://www.polymath-global.com/","https://polymathnc.com/","http://127.0.0.1:8765/","#")) else 'href="#preview-only"',preview)
preview=re.sub(r'<link\b[^>]*>',"",preview)
styles="\n".join(re.findall(r'<style[^>]*>([\s\S]*?)</style>',preview))
preview=re.sub(r'<style[^>]*>[\s\S]*?</style>',"",preview)
preview=re.sub(r'<img\b[^>]*>', '<img src="/static/logo.png" width="34" height="34" alt="Polymath Global">',preview)
preview=preview.replace("</head>",'<link rel="stylesheet" href="/preview/home.css"></head>')
(out/"home-preview.html").write_text(preview,encoding="utf-8")
(out/"home.css").write_text((home.parent/".local-html/navigation.css").read_text(encoding="utf-8")+"\n"+styles,encoding="utf-8")
print(json.dumps({"prepared":True,"source_sha256":receipt["source_sha256"],"private_index_copied":False}))
