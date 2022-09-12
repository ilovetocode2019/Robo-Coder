"""
Parses the emojis from the Discord source, and updates the emoji list file.
"""

import itertools
import json
import re
import requests

def main():
    resp = requests.get("https://raw.githubusercontent.com/Discord-Datamining/Discord-Datamining/master/current.js")
    src = resp.text
    match = re.search(r"503033:[^\']+(.+)\'", src)
    emojis = json.loads(match.group(1)[1:])

    parsed = list(itertools.chain.from_iterable([[emoji["surrogates"] for emoji in emojis[key]] for key in emojis.keys()]))

    with open("assets/emojis.json", "w") as file:
        file.write(json.dumps(parsed))

if __name__ == "__main__":
    main()
