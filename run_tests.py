#!/usr/bin/env python3
"""
Test discovery and execution runner for scfa-rl-agent.
Zero external dependencies. Runs all test_* functions in tests/*.py.
"""

import importlib
import inspect
import os
import sys
import time
import traceback
from pathlib import Path


def run_all_tests():
    tests_dir = Path(__file__).parent / "tests"
    sys.path.insert(0, str(Path(__file__).parent))

    test_files = sorted(tests_dir.glob("test_*.py"))
    total = 0
    passed = 0
    failed = 0
    errors = []

    print(f"Found {len(test_files)} test suite file(s) in {tests_dir}:")

    start_all = time.time()
    for tf in test_files:
        mod_name = f"tests.{tf.stem}"
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:
            print(f"❌ Failed to import {mod_name}: {e}")
            traceback.print_exc()
            failed += 1
            continue

        test_funcs = [
            (name, func)
            for name, func in inspect.getmembers(mod, inspect.isfunction)
            if name.startswith("test_")
        ]

        print(f"\n📂 {tf.name} ({len(test_funcs)} tests):")
        for name, func in test_funcs:
            total += 1
            try:
                t0 = time.time()
                func()
                dur = (time.time() - t0) * 1000.0
                passed += 1
                print(f"  ✅ {name:<45} ({dur:5.1f} ms)")
            except Exception as e:
                failed += 1
                errors.append((tf.name, name, traceback.format_exc()))
                print(f"  ❌ {name:<45} FAIL")

    elapsed = time.time() - start_all
    print("\n" + "=" * 60)
    print(f"Test Run Summary: {passed}/{total} Passed, {failed} Failed in {elapsed:.2f}s")
    print("=" * 60)

    if errors:
        print("\nFailures Detail:")
        for tf_name, test_name, tb in errors:
            print(f"\n--- {tf_name} :: {test_name} ---")
            print(tb)
        sys.exit(1)
    else:
        print("🎉 ALL TESTS PASSED SUCCESSFULLY!")
        sys.exit(0)


if __name__ == "__main__":
    run_all_tests()
