from src.tools.season_data_watch import __main__ as main_module


def test_main_reports_input_errors_as_json(capsys, tmp_path) -> None:
    exit_code = main_module.main(["--source-lock", str(tmp_path / "missing.json")])

    output = capsys.readouterr().out
    assert exit_code == 2
    assert '"status": "input_error"' in output
