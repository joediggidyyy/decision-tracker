from test_action_browser import run_browser


def test_page_layout_navigation(tmp_path):
    run_browser(tmp_path, "page_layout_browser.cjs", "page-layout-browser")
