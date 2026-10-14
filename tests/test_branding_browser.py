from test_action_browser import run_browser


def test_banner_watermarks_and_projects_landing(tmp_path):
    run_browser(tmp_path, 'branding_browser.cjs', 'record-display-browser')
