# Changelog

All notable changes to this project will be documented in this file. 

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

_Note: 'Unreleased' section below is used for untagged changes that will be issued with the next version bump_

### [Unreleased] - 2022-00-00 
#### Added
#### Changed
#### Deprecated
#### Removed
#### Fixed
#### Security
__BEGIN-CHANGELOG__
 
### [1.6.3] - 2022-04-10
#### Changed
 - optional flags documentation now have a bit clearer syntax 
#### Fixed
 - group names in command YAML now match expected pattern
#### Security
 
### [1.6.2] - 2022-04-10
#### Fixed
 - Forgot to patch commands in to `SlackBotBase`, which is where the task delegation occurs. Without this, viktor wasn't handling any command
 
### [1.6.1] - 2022-04-10
#### Added
 - Some decent test methods to start off with
#### Fixed
 - command YAML structure adjusted due to `slacktools` adjustment
 
### [1.6.0] - 2022-04-08
#### Added
 - CHANGELOG
 - pyproject.toml
 - poetry.lock
#### Changed
 - Completed switch to poetry
 - Shifted to new PPM routine for package management
#### Deprecated
 - Versioneer
#### Removed
 - Lots of PPM-dependent files

__END-CHANGELOG__