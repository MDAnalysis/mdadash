# Development

This page contains developer instructions to build and maintain `mdadash`.

- [Installation](#installation)
  - [With `conda`](#with-conda)
  - [With `pip`](#with-pip)
- [Run](#run)
- [Develop](#develop)
  - [Frontend](#frontend)
  - [Backend](#backend)
- [Lint checks](#lint-checks)
  - [Frontend](#frontend)
  - [Backend](#backend)
- [Tests](#tests)
  - [Frontend](#frontend)
  - [Backend](#backend)
- [Code Coverage](#code-coverage)
  - [Frontend](#frontend)
  - [Backend](#backend)
- [Build](#build)
- [Verify GitHub actions locally](#verify-github-actions-locally)
- [Docs](#docs)

### Installation

To build mdadash from source,we highly recommend using virtual environments. If possible, we strongly recommend that you use [Anaconda](https://docs.conda.io/en/latest/) as your package manager. Below we provide instructions both for `conda` and for `pip`.

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
mdadash --topology <topology_filename> --trajectory <trajectory_url>
```

To see the options available:

```sh
mdadash --help
```

### Develop

#### Frontend

Developer instructions for `frontend` code can be found [here](mdadash/frontend/README.md).

#### Backend

- Use the `editable` installation above (`pip install -e .`)

### Lint checks

#### Frontend

```sh
npm run lint --prefix mdadash/frontend
```

#### Backend

```sh
ruff check
```

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

To verify the created wheel in an isolated environment:

```sh
uv run --no-project --refresh --with path.to.whl mdadash <options>
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
