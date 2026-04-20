import re
import sys
from pathlib import Path


def refactor_file(filepath):
    with Path(filepath).open() as f:
        content = f.read()

    original = content

    if (
        "os.path" in content
        or "open(" in content
        or "os.remove(" in content
        or "os.getcwd(" in content
        or "os.unlink(" in content
    ) and "from pathlib import Path" not in content:
        imports = list(re.finditer(r"^(import .*|from .* import .*)$", content, re.MULTILINE))
        if imports:
            first_import = imports[0]
            content = content[: first_import.start()] + "from pathlib import Path\n" + content[first_import.start() :]
        else:
            content = "from pathlib import Path\n" + content

    for _ in range(3):
        content = re.sub(r"os\.path\.join\(([^,]+),\s*([^),]+)\)", r"(Path(\1) / \2)", content)
        content = re.sub(r"os\.path\.join\(([^,]+),\s*([^,]+),\s*([^)]+)\)", r"(Path(\1) / \2 / \3)", content)

    content = re.sub(r"os\.path\.exists\(([^)]+)\)", r"Path(\1).exists()", content)
    content = re.sub(r"os\.remove\(([^)]+)\)", r"Path(\1).unlink()", content)
    content = re.sub(r"os\.unlink\(([^)]+)\)", r"Path(\1).unlink()", content)
    content = re.sub(r"os\.path\.dirname\(([^)]+)\)", r"Path(\1).parent", content)
    content = re.sub(r"os\.path\.abspath\(([^)]+)\)", r"Path(\1).resolve()", content)
    content = re.sub(r"os\.path\.isabs\(([^)]+)\)", r"Path(\1).is_absolute()", content)
    content = re.sub(r"os\.path\.basename\(([^)]+)\)", r"Path(\1).name", content)
    content = re.sub(r"os\.getcwd\(\)", r"Path.cwd()", content)

    content = re.sub(r"with open\(([^),]+)(,\s*[^)]+)?\)", r"with Path(\1).open(\2)", content)
    content = content.replace(".open()", ".open()")  # fix empty group 2
    content = re.sub(r"\.open\((,\s*)", r".open(", content)

    content = re.sub(r"os\.path\.splitext\(([^)]+)\)\[0\]", r"Path(\1).stem", content)

    if content != original:
        with Path(filepath).open("w") as f:
            f.write(content)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        refactor_file(path)
