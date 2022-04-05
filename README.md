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
cd viktor && sh update_script.sh

# Add service file to system
sudo cp viktor.service /lib/systemd/system/
sudo chmod 644 /lib/systemd/system/cah.service
sudo systemctl daemon-reload
sudo systemctl enable cah.service
```

## Upgrade
```bash
pip3 install git+https://github.com/barretobrock/viktor.git#egg=viktor --upgrade
```

## Run
```bash
python3 run.py
```

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



