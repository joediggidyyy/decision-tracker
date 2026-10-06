from test_action_browser import run_browser

def test_planning_application_browser(tmp_path):
    run_browser(tmp_path,'application_browser.cjs','application-browser')
