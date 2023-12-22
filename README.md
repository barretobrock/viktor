# Viktor
A helpful slackbot with a heart of gold

## Info
This is really something I built for personal use. There are credential collection methods that rely on prebuilt routines that might prove specific to only my use case. Should anyone discover this and wish to use it, feel free to contact me and I'll work on adapting this to wider use cases.

## Prerequisites
 - py-package-manager cloned
 - bash enabled, not dash
 ```bash
# Check with
sh --version
# Change with
sudo dpkg-reconfigure dash
```

## Installation
```bash
cd ~/venvs && python3 -m venv viktor
source ~/venvs/viktor/bin/activate
cd ~/extras && git clone https://github.com/barretobrock/viktor.git
cd viktor && make pull
```
### Daemon installation
```bash
# Add service file to system
sudo cp viktor.service /lib/systemd/system/
sudo chmod 644 /lib/systemd/system/viktor.service
sudo systemctl daemon-reload
sudo systemctl enable viktor.service
```

### Postgres server install
```bash
sudo apt install postgresql postgresql-contrib python3.11-dev gcc libpq-dev
```

### Postgres database setup
NB! This assumes Postgres 15 is already installed on your server.

If running in a docker container, do the following to gain entry:
```bash
docker exec -it <name> bash
# Then, once in
psql -h localhost -p 5432 -U postgres
```

Enter postgres with `sudo -u postgres psql`
```postgresql
-- Create user
CREATE USER <user> WITH ENCRYPTED PASSWORD '<pwd>';
-- Create database & schema
CREATE DATABASE <db>;
-- Grant create, usage to user for public schema for shared values
GRANT USAGE, CREATE ON SCHEMA public TO <usr>;
-- Grant perms to database
GRANT ALL PRIVILEGES ON DATABASE <db> TO <usr>;
ALTER DATABASE <db> OWNER TO <usr>;
\c <db>
CREATE SCHEMA <schema>;
GRANT USAGE, CREATE ON SCHEMA <schema> TO <usr>;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA <schema> To <usr>;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA <schema> To <usr>;

```

## Upgrade
```bash
python3 -m pip install .
# or if you're me and want to complicate things for the sake of automation
sh ppmgr.sh pull
```

## Run
```bash
python3 run.py
```

## Local Development
As of April 2022, I switched over to [poetry]() to try and better wrangle with ever-changing requirements and a consistently messy setup.py file. Here's the process to rebuild a local development environment (assuming the steps in [Installation](#installation) have already been done):
### Install poetry
I followed the [guide](https://python-poetry.org/docs/#installation) in the poetry docs to install, following the guidelines for using `curl`. I'd recommend to my future self to just install with `pipx` next time, as that seems to do the trick without `curl`ing a remote file and executing :yikes: So:
```bash
# Prereq: sudo apt install pipx
pipx install poetry
# Confirm install
poetry --version
```
### Updating deps
To update, change the deps in `pyproject.toml`, then run `poetry update` to rebuild the lock file and then `poetry install` to reinstall

## Local testing

### Testing with responses
For local testing with Slack responses, get a different terminal window open and initiate `ngrok` in it to test the webhook outside of the live endpoint
```bash
ngrok http 5003
```
Then in another window, run the script to get the bot/app running. Don't forget to change the URL in Slack's preferences.

## App Info

### Permissions
#### Events
 - Bot
   - emoji_changed
   - message.channels
   - message.groups
   - message.im
   - pin_added
   - pin_removed
   - reaction_added
   - user_change
 - User
   - None, ATM
#### OAuth Scopes
 - Bot
   - channels.history
   - *channels.join
   - channels.read
   - chat.write
   - commands (slash)
   - emoji.read
   - files.write
   - groups.history
   - groups.read
   - im.history
   - im.read
   - im.write
   - *incoming-webhook (CURL-based notifications)
   - mpim.read
   - pins.read
   - reactions.read
   - reactions.write
   - users.read
 - User
   - search.read

 .* = Not necessary for the primary functions of the service.
