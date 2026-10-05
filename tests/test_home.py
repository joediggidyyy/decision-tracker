import json
from pathlib import Path
from html.parser import HTMLParser

class Parser(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=="a":self.links.append(dict(attrs))

def test_scoped_home_edit_preserves_sites_and_pending_card():
 root=Path(__file__).resolve().parents[1]
 value=json.loads((root/".local/home-integration/scoped-change.json").read_text(encoding="utf-8"))
 old=Parser();old.feed(value["prior_section"])
 new=Parser();new.feed(value["replacement_section"]+value["inserted_section"])
 prior={x["href"] for x in old.links}
 assert prior.issubset({x["href"] for x in new.links})
 launch=next(x for x in new.links if x["href"]=="http://127.0.0.1:8765/")
 assert launch["target"]=="_blank" and set(launch["rel"].split())=={"noopener","noreferrer"}
 assert "Sites and tools" not in value["replacement_section"]
 assert '<h2 id="connected-heading">Sites</h2>' in value["replacement_section"]
 assert 'id="ledger-pending"' not in value["replacement_section"]
 assert 'id="ledger-pending"' in value["inserted_section"]
 assert value["insertion_marker"].endswith('aria-labelledby="workspace-heading">')
 preview=(root/".local/home-integration/home-preview.html").read_text(encoding="utf-8")
 assert "navigation.js" not in preview and "token=" not in preview
 assert preview.index('id="tools-heading"')<preview.index('id="workspace-heading"')<preview.index('id="connected-heading"')
