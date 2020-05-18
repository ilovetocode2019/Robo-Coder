import os
import pathlib
import codecs
def get_lines_of_code():
    total = 0
    file_amount = 0
    for path, subdirs, files in os.walk("."):
        for name in files:
            if name.endswith(".py"):
                file_amount += 1
                with codecs.open(
                    "./" + str(pathlib.PurePath(path, name)), "r", "utf-8"
                ) as f:
                    for i, l in enumerate(f):
                        if (
                            l.strip().startswith("#") or len(l.strip()) == 0
                        ):  # skip commented lines.
                            pass
                        else:
                            total += 1
    return f"I am made of {total:,} lines of Python, spread across {file_amount:,} files!"

print(get_lines_of_code())