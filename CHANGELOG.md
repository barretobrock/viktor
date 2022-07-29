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

### [1.6.11] - 2022-06-07
#### Added
 - `^get\s?fa[hr]t` command

### [1.6.10] - 2022-05-19
#### Removed
 - Log entries that were too verbose
#### Fixed
 - Logic in action processing that expected uniform event dictionary structure
#### Security

### [1.6.9] - 2022-05-14
#### Added
 - Table transfer script
 - Response in thread now supported
#### Changed
 - Completed upgrade to Python 3.10
#### Fixed
 - Action shortcuts can now be properly called

### [1.6.8] - 2022-04-18
#### Added
 - error catching to API endpoints

### [1.6.7] - 2022-04-18
#### Changed
 - Removed emoji scraper into own crontab-able script

### [1.6.6] - 2022-04-18
#### Fixed
 - Potential emoji report wasn't performing the emoji scraping part

### [1.6.5] - 2022-04-18
#### Added
 - help search functionality
 - user info update broken out so procedure can be shared (to be implemented later)
 - potential emojis logging endpoint
#### Changed
 - `wfhtime` broken out into standard and nonstandard time increments for sanity
 - cron jobs API broken out into own file via blueprint

### [1.6.4] - 2022-04-15
#### Added
 - built-out command search logic
#### Changed
 - phrases, compliments, insults now pull randomly from database instead of downloading all the info first and randomly selecting

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
