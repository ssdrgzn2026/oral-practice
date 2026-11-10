# -*- coding: utf-8 -*-
"""可灵API配置模板。复制本文件为 config.py 并填入真实密钥（config.py 已被 gitignore）。"""
import os

API_KEY = os.environ.get('KLING_API_KEY', '在这里填入你的可灵API-KEY')
BASE_URL = 'https://api-beijing.klingai.com'
