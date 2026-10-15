from test_action_browser import run_browser


def test_coherent_refresh_and_modal_recovery(tmp_path):
    run_browser(tmp_path, 'refresh_browser.cjs', 'refresh-browser')


def test_browser_update_pass(tmp_path):
    run_browser(tmp_path, 'browser_update_browser.cjs', 'browser-update')
