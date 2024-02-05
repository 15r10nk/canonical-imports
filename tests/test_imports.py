import re
from pathlib import Path

from canonical_imports._core import main
from click.testing import CliRunner
from inline_snapshot import snapshot


def check(
    files, file_args=None, args=[], no=[], changed_files={}, stdout="", stderr=""
):
    runner = CliRunner(mix_stderr=False)

    def normalize(text):
        if " \n" in text:
            text = text.replace("\n", "\u23CE\n")
        text = re.sub(
            r"^\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d", "<date_time>", text, re.MULTILINE
        )
        return text

    with runner.isolated_filesystem():
        for name, content in files.items():
            d = Path(name)
            d.parent.mkdir(exist_ok=True, parents=True)
            if isinstance(content, str):
                d.write_text(content)
            elif isinstance(content, bytes):
                d.write_bytes(content)
            else:
                assert False

        no = [f"--no={e}" for e in no]

        if file_args is None:
            file_args = list(files.keys())

        result = runner.invoke(main, file_args + no + args, catch_exceptions=False)
        assert normalize(result.stderr) == stderr
        assert normalize(result.stdout) == stdout

        assert result.exit_code == 0

        changed = {}
        for name, content in files.items():
            d = Path(name)
            if isinstance(content, str):
                new_content = d.read_text()
            elif isinstance(content, bytes):
                new_content = d.read_bytes()
            else:
                assert False

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
        args=["-w"],
        changed_files=snapshot({"m/a.py": "from .c import f"}),
        stdout=snapshot(
            """\
fix: m/a.py
"""
        ),
        stderr=snapshot(""),
    )


def test_unicode_problem():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
            "m/b.py": b'print("b\xf6se")\n',
        },
        args=["-w"],
        changed_files=snapshot({}),
        stdout=snapshot(
            """\
<date_time> [error    ] could not decode m/b.py
"""
        ),
        stderr=snapshot(""),
    )


def test_preview():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
            "m/b.py": "from .c import f",
            "m/c.py": "def f():pass",
        },
        changed_files=snapshot({}),
        stdout=snapshot(
            """\
⏎
                                     m/a.py                                     ⏎
⏎
                                                                                ⏎
 @@ -1 +1 @@                                                                    ⏎
                                                                                ⏎
 -from .b import f                                                              ⏎
 +from .c import f                                                              ⏎
                                                                                ⏎
⏎
────────────────────────────────────────────────────────────────────────────────⏎
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
        args=["-w"],
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
        args=["-w"],
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
        args=["-w"],
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
        args=["-w"],
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
        args=["-w"],
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
        args=["-w"],
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
        args=["-w"],
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
        args=["-w"],
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
        args=["-w"],
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
        args=["-w"],
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
        args=["-w"],
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
        args=["-w"],
        file_args=["m/a.py"],
        changed_files=snapshot({}),
        stdout=snapshot(
            """\
<date_time> [error    ] could not parse m/b.py
"""
        ),
        stderr=snapshot(""),
    )


def test_module_not_found():
    check(
        files={
            "m/__init__.py": "",
            "m/a.py": "from .b import f",
        },
        args=["-w"],
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
        args=["-w"],
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
        args=["-w"],
        no=["public-private"],
        changed_files=snapshot({"m/a.py": "from .c import f"}),
        stdout=snapshot(
            """\
fix: m/a.py
"""
        ),
        stderr=snapshot(""),
    )
