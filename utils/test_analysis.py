import re
from collections import Counter

error_pattern = re.compile(r'([A-Za-z]+Error|Exception)')

with open("pytest_log.txt", "r", encoding="utf-8") as f:
    text = f.read()

errors = error_pattern.findall(text)

counts = Counter(errors)

print("\nError Type Summary\n------------------")
for err, count in counts.most_common():
    print(f"{err:25} {count}")