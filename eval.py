import requests

API_URL = "http://127.0.0.1:8000/ask"

TEST_CASES = [
    {
        "name": "Direct Fact - Casual Leave Carry-Forward",
        "question": "How many casual leave days can I carry forward?",
        "expect_grounded": True,
        "expected_doc": "Leave Policy",
        "expected_keyword": "8",
    },
    {
        "name": "Table Lookup - Standard Dental Implants",
        "question": "Does the Standard health tier cover dental implants?",
        "expect_grounded": True,
        "expected_doc": "Benefits Policy",
        "expected_keyword": "not covered",
    },
    {
        "name": "Table Lookup - Band C Annual LTA Limit",
        "question": "What is the annual LTA limit for Band C?",
        "expect_grounded": True,
        "expected_doc": "Benefits Policy",
        "expected_keyword": "75,000",
    },
    {
        "name": "Explicit Exclusion - Home Gym Expense",
        "question": "Can I expense a personal home gym?",
        "expect_grounded": True,
        "expected_doc": "Benefits Policy",
        "expected_keyword": "not",
    },
    {
        "name": "IT Security - Lost Laptop Reporting Window",
        "question": "How quickly must I report a stolen company laptop?",
        "expect_grounded": True,
        "expected_doc": "IT Security Policy",
        "expected_keyword": "4 hours",
    },
    {
        "name": "Table Lookup - Restricted Data Storage",
        "question": "Where am I allowed to store Restricted data like production credentials?",
        "expect_grounded": True,
        "expected_doc": "IT Security Policy",
        "expected_keyword": "secret manager",
    },
    {
        "name": "Off-Policy Trap - Relocation Bonus",
        "question": "How much relocation bonus do I get if I move to Bengaluru?",
        "expect_grounded": False,
        "expected_doc": None,
        "expected_keyword": "contact hr",
    },
    {
        "name": "Completely Unrelated Question",
        "question": "What is the capital of France?",
        "expect_grounded": False,
        "expected_doc": None,
        "expected_keyword": "contact hr",
    },
]


def run_eval():
    passed = 0
    print(f"Running {len(TEST_CASES)} evaluation tests...\n" + "=" * 60)

    for tc in TEST_CASES:
        res = requests.post(API_URL, json={"question": tc["question"]}, timeout=30).json()
        grounded_ok = res["grounded"] == tc["expect_grounded"]
        keyword_ok = tc["expected_keyword"].lower() in res["answer"].lower()

        if tc["expected_doc"]:
            doc_ok = any(tc["expected_doc"].lower() in c["document"].lower() for c in res["citations"])
        else:
            doc_ok = len(res["citations"]) == 0

        success = grounded_ok and keyword_ok and doc_ok
        status = "PASS" if success else "FAIL"
        if success:
            passed += 1

        print(f"[{status}] {tc['name']}")
        print(f"   Q: {tc['question']}")
        print(f"   A: {res['answer']}")
        print(f"   Citations: {res['citations']}\n")

    print("=" * 60)
    print(f"Score: {passed}/{len(TEST_CASES)} passed")


if __name__ == "__main__":
    run_eval()