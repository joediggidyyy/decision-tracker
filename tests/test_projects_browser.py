from test_action_browser import run_browser

def test_projects_browser(tmp_path):
    run_browser(tmp_path,"projects_browser.cjs","projects-browser")
