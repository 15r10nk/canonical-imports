<!-- -8<- [start:Header] -->


[![Docs](https://img.shields.io/badge/docs-mkdocs-green)](https://15r10nk.github.io/canonical-imports/)
[![pypi version](https://img.shields.io/pypi/v/canonical-imports.svg)](https://pypi.org/project/canonical-imports/)
![Python Versions](https://img.shields.io/pypi/pyversions/canonical-imports)
![PyPI - Downloads](https://img.shields.io/pypi/dw/canonical-imports)
[![coverage](https://img.shields.io/badge/coverage-100%25-blue)](https://15r10nk.github.io/canonical-imports/contributing/#coverage)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/15r10nk)](https://github.com/sponsors/15r10nk)

<!-- -8<- [end:Header] -->

Managing imports is difficult when the project grows in size. Functions and classes gets moved or renamed.
`canonical-imports` follows your imports and finds out where the things you are importing are actually defined.
It can change your imports which makes your code cleaner and maybe even faster.

## Installation


This project is currently only available for insiders, which mean that you can get access to it if you [sponsor](https://github.com/sponsors/15r10nk) me.
You should then have access to [this repository](https://github.com/15r10nk-insiders/canonical-imports).

You can install it with pip and the github url.

``` bash
pip install git+ssh://git@github.com/15r10nk-insiders/canonical-imports.git@insider 
```

## Key Features

- follow imports to their definition and replace them.
- options to prevent the following of some types of imports (from public to private modules).


I will show you what it does with the following example:

``` python 
# m/a.py
from ._core import helper

# m/_core.py
from ._utils import helper

# m/_utils.py

def helper():
    print("some help")
```

`helper` was moved from `_core` to `_utils`

``` bash
canonical-imports -w m/a.py
```

changes `m/a.py` to:

``` python
# m/a.py
from ._utils import helper
```


## Usage

You can use `canonical-imports` from the command line to fix some files.

```bash
canonical-imports my_package/something.py
```

Use `canonical-imports --help` for more options.

<!-- -8<- [start:Feedback] -->
## Issues

If you encounter any problems, please [report an issue](https://github.com/15r10nk/canonical-imports/issues) along with a detailed description.
<!-- -8<- [end:Feedback] -->

## License

Distributed under the terms of the [MIT](http://opensource.org/licenses/MIT) license, "canonical-imports" is free and open source software.
