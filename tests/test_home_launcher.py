"""Home generation must invoke managed startup, including with a stopped service."""
import json
from pathlib import Path
import subprocess
import sys
from html.parser import HTMLParser


def test_generated_home_uses_managed_launch(tmp_path):
    home = tmp_path / 'home.html'
    (tmp_path / '.local-html').mkdir()
    (tmp_path / '.local-html/navigation.css').write_text('', encoding='utf-8')
    home.write_text('<html><head></head><body>'
        '<section class="home-section" aria-labelledby="workspace-heading">Workspace</section>'
        '<section><h2 id="connected-heading">Sites and tools</h2>'
        '<a href="https://example.invalid/">Existing site</a>'
        '<a id="ledger-pending" href="#ledger-pending">Ledger</a></section>'
        '</body></html>', encoding='utf-8')
    output = tmp_path / 'prepared'
    result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'tools/prepare_home.py'),
        '--home', str(home), '--output', str(output)], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    receipt = json.loads((output / 'scoped-change.json').read_text(encoding='utf-8'))
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.links = []
        def handle_starttag(self, tag, attrs):
            if tag == 'a': self.links.append(dict(attrs))
    for content in [receipt['inserted_section'], (output / 'home-preview.html').read_text(encoding='utf-8')]:
        parsed = Links(); parsed.feed(content)
        launch = next(a for a in parsed.links if a.get('href') == 'decision-tracker://open')
        assert 'target' not in launch  # OS handler opens the browser only after readiness.
        assert not any(a.get('href', '').startswith('http://127.0.0.1:') for a in parsed.links)
    assert 'https://example.invalid/' in receipt['replacement_section']
    assert 'id="ledger-pending"' in receipt['inserted_section']
