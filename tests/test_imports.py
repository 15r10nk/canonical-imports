from pathlib import Path

from canonical_imports._core import main
from click.testing import CliRunner
from inline_snapshot import snapshot


def check(files, file_args=None, no=[], changed_files={}, stdout="", stderr=""):
    runner = CliRunner(mix_stderr=False)

    with runner.isolated_filesystem():
        for name, content in files.items():
            d = Path(name)
            d.parent.mkdir(exist_ok=True, parents=True)
            d.write_text(content)

        no = [f"--no={e}" for e in no]

        if file_args is None:
            file_args = list(files.keys())

        result = runner.invoke(main, file_args + no, catch_exceptions=False)
        # print(result.stdout)
        assert result.stderr == stderr
        assert result.stdout == stdout

        assert result.exit_code == 0

        changed = {}
        for name, content in files.items():
            d = Path(name)
            new_content = d.read_text()
            if new_content != content:
                changed[name] = new_content

    assert changed == changed_files


def test_simple_indirect():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
            "m/b.py": "from .c import f",
            "m/c.py": "def f():pass",
        },
        changed_files=snapshot({"m/a.py": "from .c import f"}),
        stdout=snapshot(
            """\
fix: m/a.py
"""
        ),
        stderr=snapshot(""),
    )


def test_no_init_module():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .q import f",
            "m/q/__init__.py": "from .b import f",
            "m/q/b.py": "def f():pass",
        },
        changed_files=snapshot({"m/a.py": "from .q.b import f"}),
        stdout=snapshot(
            """\
fix: m/a.py
"""
        ),
        stderr=snapshot(""),
    )

    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
            "m/b.py": "from .q import f",
            "m/q/__init__.py": "from .c import f",
            "m/q/c.py": "def f():pass",
        },
        no=["into-init"],
        changed_files=snapshot({"m/a.py": "from .q import f"}),
        stdout=snapshot(
            """\
fix: m/a.py
"""
        ),
        stderr=snapshot(""),
    )


def test_double_import():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
            "m/b.py": "from .c import f\nfrom .d import f",
            "m/c.py": "def f():pass",
            "m/d.py": "def f():pass",
        },
        changed_files=snapshot({}),
        stdout=snapshot(""),
        stderr=snapshot(""),
    )


def test_import_override():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
            "m/b.py": "from .c import f\nif True: f=5",
            "m/c.py": "def f():pass",
        },
        changed_files=snapshot({}),
        stdout=snapshot(""),
        stderr=snapshot(""),
    )


def test_import_as():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import g",
            "m/b.py": "from .c import f as g",
            "m/c.py": "def f():pass",
        },
        changed_files=snapshot({"m/a.py": "from .c import f as g"}),
        stdout=snapshot(
            """\
fix: m/a.py
"""
        ),
        stderr=snapshot(""),
    )


def test_multiple_imports_to_follow():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
            "m/b.py": "from .c import g\nfrom .c import f",
            "m/c.py": "def f():pass",
        },
        changed_files=snapshot({"m/a.py": "from .c import f"}),
        stdout=snapshot(
            """\
fix: m/a.py
"""
        ),
        stderr=snapshot(""),
    )


def test_simple_indirect_to_other_file():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
            "m/b.py": "from .c import f",
            "m/c.py": "def f():pass",
        },
        file_args=["m/a.py"],
        changed_files=snapshot({"m/a.py": "from .c import f"}),
        stdout=snapshot(
            """\
fix: m/a.py
"""
        ),
        stderr=snapshot(""),
    )


def test_different_package():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from b.b import f",
            "b/__init__.py": "",
            "b/b.py": "from .c import f",
            "b/c.py": "def f():pass",
        },
        changed_files=snapshot({"m/a.py": "from b.c import f"}),
        stdout=snapshot(
            """\
fix: m/a.py
"""
        ),
        stderr=snapshot(""),
    )


def test_different_unknown_package():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from b.b import f",
        },
        changed_files=snapshot({}),
        stdout=snapshot(""),
        stderr=snapshot(""),
    )


def test_cycle():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
            "m/b.py": "from .a import f",
        },
        changed_files=snapshot({}),
        stdout=snapshot(""),
        stderr=snapshot(""),
    )


def test_import_module():
    check(
        files={
            "m/__init__.py": "from .b import f",
            "m/a.py": "from . import f",
            "m/b.py": "def f():pass",
        },
        changed_files=snapshot({"m/a.py": "from .b import f"}),
        stdout=snapshot(
            """\
fix: m/a.py
"""
        ),
        stderr=snapshot(""),
    )


def test_invalid_syntax():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
            "m/b.py": "5///4",
        },
        file_args=["m/a.py"],
        changed_files=snapshot({}),
        stdout=snapshot(""),
        stderr=snapshot(""),
    )


def test_module_not_found():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
        },
        changed_files=snapshot({}),
        stdout=snapshot(""),
        stderr=snapshot(""),
    )


def test_private_indirect():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
            "m/b.py": "from ._c import f",
            "m/_c.py": "def f():pass",
        },
        no=["public-private"],
        changed_files=snapshot({}),
        stdout=snapshot(""),
        stderr=snapshot(""),
    )

    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from ._b import f",
            "m/_b.py": "from .c import f",
            "m/c.py": "def f():pass",
        },
        no=["public-private"],
        changed_files=snapshot({"m/a.py": "from .c import f"}),
        stdout=snapshot(
            """\
fix: m/a.py
"""
        ),
        stderr=snapshot(""),
    )
