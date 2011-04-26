#!/usr/bin/python

import re

bgg_spam = re.compile('(b[bg]g[012\- ]?d?l?[012\- ]?[012\- ]?)', re.IGNORECASE)

words_to_strip = ['afk', 'away', '()', '[]', ' - ']

def norm_name(name):
    bgg_spam_match = bgg_spam.search(name)
    if bgg_spam_match:
        name = name.replace(bgg_spam_match.group(1), '')
    for word in words_to_strip:
        name = name.replace(word, '')
    return name.strip()

