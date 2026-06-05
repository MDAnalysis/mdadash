# mdadash

[//]: # "Badges"

| **Latest release** | [![Last release tag][badge_release]][url_latest_release] ![GitHub commits since latest release (by date) for a branch][badge_commits_since] [![Documentation Status][badge_docs]][url_docs] |
| :----------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Status**         | [![GH Actions Status][badge_actions]][url_actions] [![codecov][badge_codecov]][url_codecov]                                                                                                 |
| **Community**      | [![License: MIT License][badge_license]][url_license] [![Powered by MDAnalysis][badge_mda]][url_mda]                                                                                        |

[badge_actions]: https://github.com/MDAnalysis/mdadash/actions/workflows/gh-ci.yaml/badge.svg
[badge_codecov]: https://codecov.io/gh/MDAnalysis/mdadash/branch/main/graph/badge.svg
[badge_commits_since]: https://img.shields.io/github/commits-since/MDAnalysis/mdadash/latest
[badge_docs]: https://readthedocs.org/projects/mdadash/badge/?version=latest
[badge_license]: https://img.shields.io/badge/License-MIT-yellow.svg
[badge_mda]: https://img.shields.io/badge/powered%20by-MDAnalysis-orange.svg?logoWidth=16&logo=data:image/x-icon;base64,AAABAAEAEBAAAAEAIAAoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJD+XwCY/fEAkf3uAJf97wGT/a+HfHaoiIWE7n9/f+6Hh4fvgICAjwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACT/yYAlP//AJ///wCg//8JjvOchXly1oaGhv+Ghob/j4+P/39/f3IAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJH8aQCY/8wAkv2kfY+elJ6al/yVlZX7iIiI8H9/f7h/f38UAAAAAAAAAAAAAAAAAAAAAAAAAAB/f38egYF/noqAebF8gYaagnx3oFpUUtZpaWr/WFhY8zo6OmT///8BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgICAn46Ojv+Hh4b/jouJ/4iGhfcAAADnAAAA/wAAAP8AAADIAAAAAwCj/zIAnf2VAJD/PAAAAAAAAAAAAAAAAICAgNGHh4f/gICA/4SEhP+Xl5f/AwMD/wAAAP8AAAD/AAAA/wAAAB8Aov9/ALr//wCS/Z0AAAAAAAAAAAAAAACBgYGOjo6O/4mJif+Pj4//iYmJ/wAAAOAAAAD+AAAA/wAAAP8AAABhAP7+FgCi/38Axf4fAAAAAAAAAAAAAAAAiIiID4GBgYKCgoKogoB+fYSEgZhgYGDZXl5e/m9vb/9ISEjpEBAQxw8AAFQAAAAAAAAANQAAADcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAjo6Mb5iYmP+cnJz/jY2N95CQkO4pKSn/AAAA7gAAAP0AAAD7AAAAhgAAAAEAAAAAAAAAAACL/gsAkv2uAJX/QQAAAAB9fX3egoKC/4CAgP+NjY3/c3Nz+wAAAP8AAAD/AAAA/wAAAPUAAAAcAAAAAAAAAAAAnP4NAJL9rgCR/0YAAAAAfX19w4ODg/98fHz/i4uL/4qKivwAAAD/AAAA/wAAAP8AAAD1AAAAGwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAALGxsVyqqqr/mpqa/6mpqf9KSUn/AAAA5QAAAPkAAAD5AAAAhQAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADkUFBSuZ2dn/3V1df8uLi7bAAAATgBGfyQAAAA2AAAAMwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB0AAADoAAAA/wAAAP8AAAD/AAAAWgC3/2AAnv3eAJ/+dgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA9AAAA/wAAAP8AAAD/AAAA/wAKDzEAnP3WAKn//wCS/OgAf/8MAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIQAAANwAAADtAAAA7QAAAMAAABUMAJn9gwCe/e0Aj/2LAP//AQAAAAAAAAAA
[badge_release]: https://img.shields.io/github/release-pre/MDAnalysis/mdadash.svg
[url_actions]: https://github.com/MDAnalysis/mdadash/actions?query=branch%3Amain+workflow%3Agh-ci
[url_codecov]: https://codecov.io/gh/MDAnalysis/mdadash/branch/main
[url_docs]: https://mdadash.readthedocs.io/en/latest/?badge=latest
[url_latest_release]: https://github.com/MDAnalysis/mdadash/releases
[url_license]: https://opensource.org/licenses/MIT
[url_mda]: https://www.mdanalysis.org

Dashboard for tracking and analyzing live MD simulations with streaming.

mdadash is bound by a [Code of Conduct](https://github.com/MDAnalysis/mdadash/blob/main/CODE_OF_CONDUCT.md).

### Installation

To build mdadash from source,
we highly recommend using virtual environments.
If possible, we strongly recommend that you use
[Anaconda](https://docs.conda.io/en/latest/) as your package manager.
Below we provide instructions both for `conda` and
for `pip`.

#### With conda

Ensure that you have [conda](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html) installed.

Create a virtual environment and activate it:

```sh
conda create --name mdadash
conda activate mdadash
```

Install the development, testing and documentation dependencies:

```sh
conda env update --name mdadash --file devtools/conda-envs/dev_env.yaml
conda env update --name mdadash --file devtools/conda-envs/test_env.yaml
conda env update --name mdadash --file docs/requirements.yaml
```

Build this package from source:

```sh
pip install -e .
```

If you want to update your dependencies (which can be risky!), run:

```sh
conda update --all
```

And when you are finished, you can exit the virtual environment with:

```sh
conda deactivate
```

#### With pip

To build the package from source, run:

```sh
pip install .
```

If you want to create a development environment, install
the dependencies required for tests and docs with:

```sh
pip install ".[dev,test,doc]"
```

### Run

> The frontend code needs to be built before running the backend server. This can be done as follows:

```sh
cd mdadash/frontend
npm install
npm run build
```

To run the dashboard server:

```sh
mdadash
```

To see the options available:

```sh
mdadash --help
```

### Development

#### Frontend

Developer instruction for `frontend` code can be found [here](mdadash/frontend/README.md).

#### Backend

- Use the `editable` installation above (`pip install -e .`)

### Tests

#### Frontend

```sh
npm run test:unit --prefix mdadash/frontend -- --run
```

#### Backend

```sh
pytest -v
```

### Code Coverage

#### Frontend

```sh
cd mdadash/frontend
npx vitest --run --coverage
```

The coverage details will be shown on the console. Open `coverage/index.html` to view the interactive coverage report in the browser.

#### Backend

To see coverage output on the console:

```sh
pytest -v --cov=mdadash
```

To write coverage output to `html` file:

```sh
pytest -v --cov=mdadash --cov-report=html
```

Open `htmlcov/index.html` to view the coverage report in the browser.

### Build

To build this package:

```sh
rm -rf mdadash.egg-info dist && python -m build
```

To verify the created wheel:

```sh
uv run --refresh --with path.to.whl mdadash
```

To check the created distribution:

```sh
twine check dist/*
```

### Verify GitHub actions locally

GitHub actions can be verified locally using [act](https://github.com/nektos/act).

> Note that this requires [Docker](https://www.docker.com). Running on Mac needs an additional param `--container-architecture linux/arm64`. To bypass the repo name check, you can pass `--env GITHUB_REPOSITORY=MDAnalysis/mdadash`. Both these can be set in `~/.actrc` as well.

To list the jobs:

```sh
act -l
```

To run a job (eg: `pylint_check`):

```sh
act -j pylint_check
```

To run all jobs:

```sh
act
```

### Docs

Setting up the docs environment:

```sh
conda env update --name mdadash --file docs/requirements.yaml
```

Building docs locally:

```sh
cd docs
make clean && make html
```

Open `docs/_build/html/index.html` to view the docs in the browser.

### Copyright

The mdadash source code is hosted at https://github.com/MDAnalysis/mdadash
and is available under the [MIT License](https://opensource.org/licenses/MIT) (see the file [LICENSE](https://github.com/MDAnalysis/mdadash/blob/main/LICENSE)).

Copyright (c) 2026, MDAnalysis

#### Acknowledgements

Project based on the
[MDAnalysis Cookiecutter](https://github.com/MDAnalysis/cookiecutter-mda) version 0.1.
Please cite [MDAnalysis](https://github.com/MDAnalysis/mdanalysis#citation) when using mdadash in published work.
