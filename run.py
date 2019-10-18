#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from viktor import Viktor
from kavalkilu import Log, LogArgParser


# Initiate logging
log = Log('viktor', log_lvl=LogArgParser().loglvl)

viktor = Viktor(log)
try:
    viktor.run_rtm('Booted up and ready to party! :hyper-tada:', 'Daemon killed gracefully. :party-dead:')
except KeyboardInterrupt:
    log.debug('Script ended manually.')
finally:
    viktor.message_grp('Shutdown for maintenance.:dotdotdot:')

log.close()



