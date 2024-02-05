import subprocess as sp

from inline_snapshot import snapshot


def test_cli():
    result = sp.run(["canonical-imports", "--help"], capture_output=True)
    assert result.returncode == 0
    assert result.stdout.decode() == snapshot(
        """\
Usage: canonical-imports [OPTIONS] [PATHS]...

  `canonical-imports` follows your imports and finds out where the things you
  are importing are actually defined.

  PATHS: python files or directories with should be scanned for python files

Options:
  --no [public-private|into-init]
                                  Exclude specific imports
  -w, --write                     write changed imports
  --help                          Show this message and exit.
"""
    )
