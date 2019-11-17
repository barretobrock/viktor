#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import viktor
from datetime import datetime as dt
from kavalkilu import Log, LogArgParser


# Initiate logging
log = Log('viktor', log_lvl=LogArgParser().loglvl)

vbot = viktor.Viktor(log.log_name)
try:
    info_dict = {
        'bot': 'Viktor',
        'version': viktor.__version__,
        'update': dt.strptime(viktor.__update_date__, '%Y-%m-%dT%H:%M:%S%z'),
        'msg': 'Booted up and ready to party!'
    }
    bootup_msg = '```{bot:-^50}\n{version:>20} updated {update:%F %T}\n{msg:-^50}```'.format(**info_dict)
    kill_msg = 'Daemon killed, but gracefully. :party-dead:'
    vbot.run_rtm(bootup_msg, kill_msg)
except KeyboardInterrupt:
    log.debug('Script ended manually.')
finally:
    vbot.message_grp('Shutdown for maintenance.:dotdotdot:')

log.close()



