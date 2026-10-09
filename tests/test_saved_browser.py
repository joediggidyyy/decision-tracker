from test_action_browser import run_browser

def test_saved_browser(tmp_path):
    run_browser(tmp_path,'saved_browser.cjs','saved-browser')
