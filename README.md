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

## Getting Started

### Installation

`mdadash` can be installed in any of the following ways depending on your Python environment:

```sh
pip install mdadash
```

or

```sh
uv add mdadash
```

or

```sh
conda install -c conda-forge mdadash
```

or

```sh
mamba install -c conda-forge mdadash
```

To execute directly from an isolated environment without installing:

```sh
uvx mdadash -h
```

### Run

Once the package is installed, it can be run using the `mdadash` command to start the dashboard server:

```sh
mdadash --topology <topology_filename> --trajectory <trajectory_url>
```

Example:

```sh
mdadash --topology start.gro --trajectory imd://localhost:8889
```

To see a list of all the available options:

```sh
mdadash -h
```

```sh
$ mdadash -h
usage: mdadash [-h] --topology TOPOLOGY --trajectory TRAJECTORY [--dashboard-port DASHBOARD_PORT] [--dashboard-host DASHBOARD_HOST]
               [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [-v]

Start the MDA Dashboard server

options:
  -h, --help            show this help message and exit
  --topology TOPOLOGY   Topology filepath (required)
  --trajectory TRAJECTORY
                        Trajectory URL (of the form 'imd://host:port') (required)
  --dashboard-port DASHBOARD_PORT
                        Port to run the dashboard server on (default: 8000)
  --dashboard-host DASHBOARD_HOST
                        Host address to bind dashboard server to (default: 127.0.0.1)
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set the logging level (default: INFO)
  -v, --version         Show the dashboard version and exit
```

### Dashboard

The dashboard can be accessed by navigating to [`http://127.0.0.1:8000`](http://127.0.0.1:8000) from any browser.

> Note:
> Both the dashboard host and post can be customized using the `mdadash` command line options.

### Development

Developer instructions for this project can be found [here](DEVELOPMENT.md).

### Copyright

The mdadash source code is hosted at https://github.com/MDAnalysis/mdadash
and is available under the [MIT License](https://opensource.org/licenses/MIT) (see the file [LICENSE](https://github.com/MDAnalysis/mdadash/blob/main/LICENSE)).

Copyright (c) 2026, MDAnalysis

#### Acknowledgements

Project based on the
[MDAnalysis Cookiecutter](https://github.com/MDAnalysis/cookiecutter-mda) version 0.1.
Please cite [MDAnalysis](https://github.com/MDAnalysis/mdanalysis#citation) when using mdadash in published work.
