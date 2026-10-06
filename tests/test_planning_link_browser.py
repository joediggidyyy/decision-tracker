from test_action_browser import run_browser

def test_planning_link_browser(tmp_path):
    run_browser(tmp_path,'planning_link_browser.cjs','planning-link-browser')
