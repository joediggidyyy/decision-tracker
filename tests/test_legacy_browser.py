from test_action_browser import run_browser

def test_legacy_source_browser(tmp_path):
    run_browser(tmp_path,'legacy_browser.cjs','legacy-browser')
