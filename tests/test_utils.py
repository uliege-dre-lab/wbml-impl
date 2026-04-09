from wikibase_pipeline.utils.verbose_utils import inform, warn


def test_warn_prints_when_verbose_1(capsys):
    warn("test message", verbose=1)

    captured = capsys.readouterr()
    assert "Warning: test message" in captured.out


def test_warn_silent_when_verbose_0(capsys):
    warn("test message", verbose=0)

    captured = capsys.readouterr()
    assert captured.out == ""


def test_inform_prints_when_verbose_2(capsys):
    inform("hello", verbose=2)

    captured = capsys.readouterr()
    assert "Info: hello" in captured.out


def test_inform_silent_when_verbose_1(capsys):
    inform("hello", verbose=1)

    captured = capsys.readouterr()
    assert captured.out == ""
