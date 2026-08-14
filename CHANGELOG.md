# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
The rules for this file:
  * entries are sorted newest-first.
  * summarize sets of changes - don't reproduce every git log comment here.
  * don't ever delete anything.
  * keep the format consistent:
    * do not use tabs but use spaces for formatting
    * 79 char width
    * YYYY-MM-DD date format (following ISO 8601)
  * accompany each entry with github issue/PR number (Issue #xyz)
-->

## [Unreleased]

### Authors

<!-- GitHub usernames of contributors to this release -->

??/??/?? PardhavMaradani

### Added

<!-- New added features -->

### Fixed

<!-- Bug fixes -->

### Changed

<!-- Changes in existing functionality -->

### Deprecated

<!-- Soon-to-be removed features -->

### Removed

<!-- Removed features -->

## [0.0.9]

### Authors

<!-- GitHub usernames of contributors to this release -->

08/14/2026 PardhavMaradani

### Added

<!-- New added features -->

- Added built-in widgets documentation (PR #63)
- Added batching and parallel support for com distance widget (PR #64)
- Minor widget enhancements (PR #65)
- Added custom widgets documentation (PR #66)
- Added batching and parallelization documentation (PR #67)
- Added Architecture documentation (PR #68)

## [0.0.8]

### Authors

<!-- GitHub usernames of contributors to this release -->

08/09/2026 PardhavMaradani

### Added

<!-- New added features -->

- Added widget for RMSD (PR #56)
- Added widget for Native Contacts (PR #59)
- Added widget for Contacts within cutoff (PR #60)
- Added widget for number of Hydrogen bonds (PR #61)
- Added widget for Helix Analysis (PR #62)

### Fixed

<!-- Bug fixes -->

- Miscellaneous fixes (PR #50)
- Minor UI fixes (PR #51)
- Preset icons issue on Safari

### Changed

<!-- Changes in existing functionality -->

- Changed color theme to MDA colors (PR #58)

## [0.0.7]

### Authors

<!-- GitHub usernames of contributors to this release -->

08/02/2026 PardhavMaradani

### Added

<!-- New added features -->

- Added widget for MSD Analysis (PR #35)
- Added widget for generic Autocorrelation Function (ACF) (PR #37)
- Added config setting for NoJump transformation (PR #38)
- Added widget for custom code (PR #43)
- Added Notebooks support (PR #46)
- Added custom universe setup support (PR #47)
- Added support for auto refresh of widgets when class code changes (PR #48)
- Added support for cloning built-in widget code into Notebooks (PR #49)

### Changed

<!-- Changes in existing functionality -->

- Refactored code between kernel core and widget manager (PR #45)

## [0.0.6]

### Authors

<!-- GitHub usernames of contributors to this release -->

07/12/2026 PardhavMaradani

### Added

<!-- New added features -->

- Added pause support from within widgets (PR #27)
- Added alerts support (PR #29)

### Changed

<!-- Changes in existing functionality -->

- Cleaned up widget invocation (PR #36)

## [0.0.5]

### Authors

<!-- GitHub usernames of contributors to this release -->

07/05/2026 PardhavMaradani

### Added

<!-- New added features -->

- Added persistence support (PR #19)
- Added support for MDA `AnalysisBase`-based classes (PR #21)
- Optimized plot generation to improve performane and reduce memory (PR #25)
- Added widgets for Ramachandran and Janin plots (PR #26)

## [0.0.4]

### Authors

<!-- GitHub usernames of contributors to this release -->

06/28/2026 PardhavMaradani

### Added

<!-- New added features -->

- Added support to duplicate widgets (PR #13)
- Added support for batching and parallelization (PR #15)
- Added support for energy trends (PR #16)

## [0.0.3]

### Authors

<!-- GitHub usernames of contributors to this release -->

06/20/2026 PardhavMaradani

### Added

<!-- New added features -->

- Added basic widget execution framework and energy widgets (PR #8)
- Reduce package size by moving away from mdi/font to mdi/js (PR #9)
- Added support to display imdclient session info (PR #10)
- Added widget inputs support (PR #11)
- Added dashboard grid layout presets (PR #12)

## [0.0.2]

### Authors

<!-- GitHub usernames of contributors to this release -->

06/06/2026 PardhavMaradani

### Added

<!-- New added features -->

- Added overall project structure (PR #3)
- Added async jupyter kernel support (PR #4)
- Added more tests and enabled code coverage (PR #5)
- Added basic connectivity between frontend and backend (PR #6)
