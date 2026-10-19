import argparse
import json
import os
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CASES_PATH = BASE_DIR / "tests" / "eval_cases.json"
RESULTS_PATH = BASE_DIR / "tests" / "eval-results.json"
sys.path.insert(0, str(BASE_DIR))

parser = argparse.ArgumentParser()
parser.add_argument(
    "--live",
    action="store_true",
    help="Explicitly use the configured real AI provider.",
)
args = parser.parse_args()

if not CASES_PATH.exists():
    raise SystemExit(
        f"Evaluation dataset not found: {CASES_PATH}"
    )

if args.live:
    os.environ["LLM_STUB"] = "0"
    os.environ["AI_ENABLED"] = "true"
    mode = "live"
else:
    os.environ["LLM_STUB"] = "1"
    os.environ["AI_ENABLED"] = "false"
    mode = "stub"

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

from ai_service import classify_message

cases = json.loads(CASES_PATH.read_text(encoding="utf-8-sig"))
results = []

for index, case in enumerate(cases, start=1):
    expected = case["expected_category"]

    if args.live and index > 1:
        time.sleep(0.5)

    try:
        prediction = classify_message(case["text"])
        actual = prediction.category
        passed = actual == expected

        result = {
            "id": case["id"],
            "expected": expected,
            "predicted": actual,
            "passed": passed,
            "confidence": prediction.confidence,
            "reason": prediction.reason,
            "error": None,
        }

    except Exception as error:
        result = {
            "id": case["id"],
            "expected": expected,
            "predicted": None,
            "passed": False,
            "confidence": None,
            "reason": None,
            "error": type(error).__name__,
        }

    results.append(result)

    status = "PASS" if result["passed"] else "FAIL"
    print(
        f'{case["id"]}: {status} '
        f'expected={expected} '
        f'predicted={result["predicted"]}'
    )

total = len(results)
correct = sum(item["passed"] for item in results)
accuracy = correct / total if total else 0.0

report = {
    "mode": mode,
    "total_cases": total,
    "correct": correct,
    "incorrect": total - correct,
    "accuracy": round(accuracy, 4),
    "results": results,
}

RESULTS_PATH.write_text(
    json.dumps(report, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print()
print("EVALUATION_MODE =", mode)
print("TOTAL_CASES =", total)
print("CORRECT =", correct)
print("INCORRECT =", total - correct)
print(f"ACCURACY = {accuracy:.1%}")
print("REPORT =", RESULTS_PATH)

