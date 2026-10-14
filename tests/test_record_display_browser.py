from test_action_browser import run_browser


def test_record_display_and_relationship_navigation(tmp_path):
    run_browser(tmp_path, 'record_display_browser.cjs', 'record-display-browser')
