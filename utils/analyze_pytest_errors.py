import re
from collections import defaultdict

error_pattern = re.compile(r"(FAILED|ERROR)\s+(.+?)\s+-\s+([A-Za-z]+Error|Exception)")

errors = defaultdict(lambda: {"count": 0, "tests": []})
##with open("pytest_log.txt", encoding="utf-8", errors="replace") as f:

with open("gobelo_pytest_errors.log", encoding="utf8", errors="replace") as f:
    for line in f:
        match = error_pattern.search(line)
        if match:
            _, test_name, error_type = match.groups()

            errors[error_type]["count"] += 1
            errors[error_type]["tests"].append(test_name)

print("\nPYTEST ERROR ANALYSIS")
print("=" * 60)

for err, data in sorted(errors.items(), key=lambda x: x[1]["count"], reverse=True):
    print(f"\n{err}")
    print("-" * 40)
    print(f"Count: {data['count']}")
    print("Example tests:")

    for test in data["tests"][:5]:
        print("  ", test)

print("\nTotal error categories:", len(errors))