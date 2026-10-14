from test_action_browser import run_browser


def test_project_overview_sources_copy_and_navigation(tmp_path):
    run_browser(tmp_path, 'project_details_browser.cjs', 'project-details-browser')
