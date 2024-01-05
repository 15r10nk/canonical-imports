import ast
import collections
import copy
import difflib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import asttokens
import click
from rich import print as rprint
from rich.markdown import Markdown

from ._utils import unparse


def is_private(name: str):
    return len(name) >= 2 and name[0] == "_" and name[1] != "_"


def is_module_private(module_name: str):
    return any(is_private(name) for name in module_name.split("."))


@dataclass
class Import:
    module: str
    name: str
    asname: Optional[str]

    def is_private(self):
        return is_private(self.name) or is_module_private(self.module)

    @classmethod
    def from_ast(cls, stmt: ast.ImportFrom, module: str):
        for name in stmt.names:
            module_parts = []
            if stmt.level != 0:
                module_parts = module.split(".")[: -(stmt.level)]

            if stmt.module:
                module_parts.append(stmt.module)

            yield Import(".".join(module_parts), name.name, name.asname or name.name)

    def is_inside(self, other):
        return self.module.startswith(other.module + ".")


class Module:
    def __init__(self, path, import_fixer):
        self.path = path
        self.imports = []
        self.import_fixer = import_fixer
        p = path
        m = [p.stem]
        p = p.parent

        package_folder = p

        while (p / "__init__.py").exists():
            package_folder = p
            m.insert(0, p.name)
            p = p.parent

        self.module = ".".join(m)
        self.module_parts = m

        import_fixer.register(self, package_folder)

        try:
            self.atok = asttokens.ASTTokens(self.path.read_text(), parse=True)
        except SyntaxError:
            pass
        else:
            assigned_names = {
                name.id
                for name in ast.walk(self.tree)
                if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store)
            }

            imported_names = collections.Counter(
                stmt.asname or stmt.name
                for stmt in ast.walk(self.tree)
                if isinstance(stmt, ast.alias)
            )

            double_imports = {
                name for name, count in imported_names.items() if count >= 2
            }

            for stmt in self.tree.body:
                if isinstance(stmt, ast.ImportFrom):
                    for i in Import.from_ast(stmt, self.module):
                        if (
                            i.asname not in assigned_names
                            and i.asname not in double_imports
                        ):
                            self.imports.append(i)

    def is_init(self):
        return self.path.name == "__init__.py"

    def relative_to_me(self, name):
        assert name[0] != "."
        assert name != self.module

        self_parts = list(self.module_parts)
        name_parts = name.split(".")
        if name_parts[0] != self_parts[0]:
            return {"level": 0, "module": name}

        while name_parts and self_parts and name_parts[0] == self_parts[0]:
            name_parts.pop(0)
            self_parts.pop(0)

        return {"level": len(self_parts), "module": ".".join(name_parts)}

    @property
    def tree(self):
        return self.atok.tree

    def __repr__(self):
        return f"Module({self.path!r})"  # pragma: no cover

    def lookup(self, name) -> Optional[Import]:
        for import_ in self.imports:
            if import_.asname == name:
                return import_

    def change_set(self):
        changes = []

        for stmt in ast.walk(self.tree):
            if isinstance(stmt, ast.ImportFrom):
                new_imports = {}  # name -> module
                for first_import in Import.from_ast(stmt, self.module):
                    last_import = first_import

                    step = 0

                    all_imports = [first_import]

                    skip = False

                    while True:
                        step += 1
                        if step > 50:
                            skip = True
                            break
                        module = self.import_fixer.lookup_module(last_import.module)
                        if module is None:
                            break
                        new_import = module.lookup(last_import.name)

                        if new_import != None:
                            last_import = new_import
                            all_imports.append(new_import)
                        else:
                            break

                    if skip:
                        continue

                    for i in reversed(range(1, len(all_imports))):
                        if self.import_fixer.is_allowed(
                            self.module, all_imports[: i + 1]
                        ):
                            new_imports[first_import.asname] = all_imports[i]
                            break

                m = ast.Module(body=[], type_ignores=[])

                by_module = defaultdict(list)
                for import_name, import_ in new_imports.items():
                    by_module[import_.module].append((import_name, import_))

                for module, imports in by_module.items():
                    m.body.append(
                        ast.ImportFrom(
                            **self.relative_to_me(module),
                            names=[
                                ast.alias(
                                    name=import_.name,
                                    asname=(
                                        import_name
                                        if import_name != import_.name
                                        else None
                                    ),
                                )
                                for import_name, import_ in imports
                            ],
                        )
                    )

                new_stmt = copy.deepcopy(stmt)

                new_stmt.names = [
                    n for n in stmt.names if (n.asname or n.name) not in new_imports
                ]

                if new_stmt.names:
                    m.body.append(new_stmt)

                if new_imports:
                    indent = " " * stmt.first_token.start[1]
                    changes.append(
                        (
                            stmt.first_token.startpos,
                            stmt.last_token.endpos,
                            unparse(m).replace("\n", "\n" + indent),
                        )
                    )

        return ChangeSet(self.path, changes)


class ChangeSet:
    def __init__(self, path, changes):
        self.path = path
        self.changes = changes

    def __bool__(self):
        return bool(self.changes)

    def preview(self):
        old_code = self.path.read_text()
        new_code = asttokens.util.replace(old_code, self.changes)

        diff = difflib.unified_diff(
            old_code.splitlines(),
            new_code.splitlines(),
        )
        return diff

    def fix(self):
        old_code = self.path.read_text()
        self.path.write_text(asttokens.util.replace(old_code, self.changes))


class ImportFixer:
    def __init__(self, flags):
        self.module_cache = {}
        self.package_cache = {}  # package_name -> folder
        self.flags = flags

    def is_allowed(self, module, import_chain):
        if "public-private" in self.flags:
            last_import = import_chain[-1]
            if not is_module_private(module) and last_import.is_private():
                return False

        if "into-init" in self.flags:
            if any(
                self.is_init(init.module)
                and all(imp.is_inside(init) for imp in import_chain[i + 1 :])
                for i, init in enumerate(import_chain[:-1])
            ):
                return False
        return True

    def register(self, module, package_folder):
        self.package_cache[module.module_parts[0]] = package_folder

        self.module_cache[module.path] = module

    def lookup_file(self, filename) -> Module:
        if filename not in self.module_cache:
            return Module(filename, self)
        return self.module_cache[filename]

    def lookup_module(self, module: str) -> Optional[Module]:
        module_parts = module.split(".")
        package_name = module_parts[0]
        if package_name not in self.package_cache:
            return None

        f = self.package_cache[package_name].joinpath(*module_parts[1:])
        for option in (f.with_suffix(".py"), f / "__init__.py"):
            if option.exists():
                return self.lookup_file(option)
        else:
            return

    def is_init(self, module_name: str):
        module = self.lookup_module(module_name)
        return module is not None and module.is_init()


@click.command()
@click.option(
    "--no",
    help="Exclude specific imports",
    multiple=True,
    type=click.Choice(["public-private", "into-init"]),
)
@click.option("--write", "-w", is_flag=True, help="write changed imports")
@click.argument("files", nargs=-1, type=click.Path(exists=True))
def main(no, files, write):
    import_fixer = ImportFixer(set(no))

    source_files = [Module(Path(file), import_fixer) for file in files]

    if write:
        for file in source_files:
            change_set = file.change_set()
            if change_set:
                print(f"fix: {file.path}")
                change_set.fix()
    else:
        text = []
        for file in source_files:
            change_set = file.change_set()
            if change_set:
                text.append(f"## {file.path}")
                text.append("```diff")
                text += list(change_set.preview())[2:]
                text.append("```")
                text.append("---")

        rprint(Markdown("\n".join(text), code_theme="vim"))
