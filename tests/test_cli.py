import subprocess as sp

from inline_snapshot import snapshot


def test_cli():
    result = sp.run(["canonical-imports", "--help"], capture_output=True)
    assert result.returncode == 0
    assert result.stdout.decode() == snapshot(
        """\
Usage: canonical-imports [OPTIONS] [FILES]...

Options:
  --no [public-private|into-init]
                                  Exclude specific imports
  -w, --write TEXT                write changed imports
  --help                          Show this message and exit.
"""
    )
