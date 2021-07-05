#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
os.environ['VIKTOR_ENV'] = "DEVELOPMENT"
from viktor.app import app


@app.route('/')
def index():
    return 'VIKTOR'


if __name__ == '__main__':
    app.run(port=5003)
