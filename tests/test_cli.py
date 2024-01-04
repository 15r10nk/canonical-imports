import subprocess as sp


def test_cli():
    result = sp.run(["canonical-imports"])
    assert result.returncode == 0
