"""
QA Test Intelligence Agent - MongoDB Seed Script
-------------------------------------------------
Populates qa_intelligence database with 30 days of realistic
test run history, including baked-in flaky test patterns.

Usage:
  1. pip install pymongo
  2. Replace YOUR_PASSWORD below with your actual password
  3. python seed_qa_data.py
"""

from pymongo import MongoClient
from datetime import datetime, timedelta
import random
import math

# -------------------------------------------------------
# CONFIGURATION — replace YOUR_PASSWORD with your password
# -------------------------------------------------------
CONNECTION_STRING = "mongodb+srv://nrjtcards_db_user:PASSWORD0.wigm8nq.mongodb.net/?appName=Cluster0"
DB_NAME = "qa_intelligence"

# -------------------------------------------------------
# TEST SUITE DEFINITIONS
# -------------------------------------------------------
TESTS = [
    # (test_id, test_name, suite, base_pass_rate)
    # Stable tests
    ("auth.login.valid_credentials",        "Valid credentials login",           "auth",      0.97),
    ("auth.login.invalid_password",         "Invalid password rejected",         "auth",      0.98),
    ("auth.logout.session_cleared",         "Session cleared on logout",         "auth",      0.99),
    ("auth.password_reset.email_sent",      "Password reset email sent",         "auth",      0.96),

    # Flaky tests (low pass rate, inconsistent)
    ("auth.oauth.google_callback",          "Google OAuth callback",             "auth",      0.55),  # Very flaky
    ("checkout.payment.stripe_redirect",    "Stripe payment redirect",           "checkout",  0.60),  # Flaky
    ("checkout.cart.concurrent_update",     "Concurrent cart update",            "checkout",  0.65),  # Flaky

    # Mostly stable
    ("checkout.cart.add_item",              "Add item to cart",                  "checkout",  0.95),
    ("checkout.cart.remove_item",           "Remove item from cart",             "checkout",  0.97),
    ("checkout.order.confirmation_email",   "Order confirmation email",          "checkout",  0.93),

    # Flaky under load
    ("api.users.list_paginated",            "List users paginated",              "api",       0.70),  # Flaky
    ("api.users.create",                    "Create user",                       "api",       0.96),
    ("api.users.delete",                    "Delete user",                       "api",       0.97),
    ("api.products.search",                 "Product search",                    "api",       0.94),
    ("api.products.filter",                 "Product filter",                    "api",       0.91),

    # Timing-sensitive (flaky at peak hours)
    ("notifications.email.send_bulk",       "Bulk email send",                   "notifications", 0.62),  # Flaky
    ("notifications.push.delivery",        "Push notification delivery",         "notifications", 0.88),
    ("notifications.sms.verify_code",      "SMS verification code",              "notifications", 0.72),  # Somewhat flaky

    # Stable DB tests
    ("db.migrations.run_latest",            "Run latest migrations",             "database",  0.99),
    ("db.backup.create_snapshot",           "Create DB snapshot",                "database",  0.95),
]

BRANCHES = ["main", "main", "main", "develop", "develop", "feature/auth-v2", "feature/checkout-redesign"]
ENVIRONMENTS = ["staging", "staging", "production", "production", "qa"]
PIPELINES = ["ci-pipeline", "ci-pipeline", "nightly-run", "manual-trigger"]

def is_peak_hour(dt):
    """Peak hours: 9am-12pm and 2pm-5pm UTC (simulate load-related flakiness)"""
    return dt.hour in range(9, 12) or dt.hour in range(14, 17)

def get_pass_rate(test_id, dt, branch):
    """Adjust pass rate based on time and branch context"""
    base = next(t[3] for t in TESTS if t[0] == test_id)

    # Flaky tests get worse during peak hours
    if is_peak_hour(dt) and base < 0.75:
        base *= 0.75

    # Flaky tests slightly better on feature branches (less traffic)
    if branch.startswith("feature/") and base < 0.75:
        base = min(base * 1.15, 0.85)

    return base

def generate_test_runs():
    runs = []
    now = datetime.utcnow()
    start = now - timedelta(days=30)

    for test_id, test_name, suite, _ in TESTS:
        # Each test runs ~4-8 times per day
        runs_per_day = random.randint(4, 8)
        current = start

        while current < now:
            for _ in range(runs_per_day):
                branch = random.choice(BRANCHES)
                environment = random.choice(ENVIRONMENTS)
                pipeline = random.choice(PIPELINES)

                pass_rate = get_pass_rate(test_id, current, branch)
                passed = random.random() < pass_rate

                # Duration: flaky tests tend to timeout (longer duration on fail)
                base_duration = random.randint(200, 800)
                if not passed:
                    duration = random.randint(1500, 5000)  # Timeout-like
                else:
                    duration = base_duration + random.randint(-100, 300)

                # Retries: more retries on flaky tests
                retry_count = 0
                if not passed and pass_rate < 0.75:
                    retry_count = random.randint(1, 3)

                run = {
                    "test_id": test_id,
                    "test_name": test_name,
                    "suite": suite,
                    "status": "passed" if passed else "failed",
                    "duration_ms": duration,
                    "branch": branch,
                    "environment": environment,
                    "run_by": pipeline,
                    "timestamp": current + timedelta(
                        hours=random.randint(0, 23),
                        minutes=random.randint(0, 59)
                    ),
                    "error_message": None if passed else random.choice([
                        "Timeout waiting for response",
                        "Expected 200 but got 504",
                        "Connection reset by peer",
                        "AssertionError: expected true but got false",
                        "Network error: ECONNREFUSED",
                    ]),
                    "retry_count": retry_count,
                }
                runs.append(run)

            current += timedelta(days=1)

    return runs


def compute_flaky_alerts(test_runs):
    """Analyze test runs and generate flaky alert documents"""
    from collections import defaultdict

    # Group last 14 days of runs by test_id
    cutoff = datetime.utcnow() - timedelta(days=14)
    recent = [r for r in test_runs if r["timestamp"] >= cutoff]

    by_test = defaultdict(list)
    for r in recent:
        by_test[r["test_id"]].append(r)

    alerts = []
    for test_id, runs in by_test.items():
        total = len(runs)
        failures = sum(1 for r in runs if r["status"] == "failed")
        flakiness_score = round(failures / total, 2) if total > 0 else 0

        # Only alert if flakiness score is significant
        if flakiness_score < 0.15:
            continue

        # Find pattern
        staging_fails = sum(1 for r in runs if r["status"] == "failed" and r["environment"] == "staging")
        prod_fails = sum(1 for r in runs if r["status"] == "failed" and r["environment"] == "production")
        peak_fails = sum(1 for r in runs if r["status"] == "failed" and is_peak_hour(r["timestamp"]))

        pattern_parts = []
        if staging_fails > prod_fails * 1.5:
            pattern_parts.append("worse on staging than production")
        if peak_fails > failures * 0.5:
            pattern_parts.append("tends to fail during peak hours (9am-5pm UTC)")
        avg_retry = sum(r["retry_count"] for r in runs if r["status"] == "failed") / max(failures, 1)
        if avg_retry > 1:
            pattern_parts.append(f"averages {avg_retry:.1f} retries per failure")

        pattern_notes = "; ".join(pattern_parts) if pattern_parts else "No clear environmental pattern detected"

        test_name = runs[0]["test_name"]
        alerts.append({
            "test_id": test_id,
            "test_name": test_name,
            "detected_at": datetime.utcnow(),
            "flakiness_score": flakiness_score,
            "recent_runs": total,
            "failures": failures,
            "pattern_notes": pattern_notes,
            "status": "open",
            "severity": "high" if flakiness_score > 0.4 else "medium",
        })

    # Sort by flakiness score descending
    alerts.sort(key=lambda x: x["flakiness_score"], reverse=True)
    return alerts


def main():
    print("Connecting to MongoDB Atlas...")
    client = MongoClient(CONNECTION_STRING)
    db = client[DB_NAME]

    # Clear existing data
    print("Clearing existing data...")
    db.test_runs.delete_many({})
    db.flaky_alerts.delete_many({})

    # Generate and insert test runs
    print("Generating 30 days of test run history...")
    runs = generate_test_runs()
    db.test_runs.insert_many(runs)
    print(f"  ✓ Inserted {len(runs)} test run documents")

    # Compute and insert flaky alerts
    print("Computing flaky test patterns...")
    alerts = compute_flaky_alerts(runs)
    db.flaky_alerts.insert_many(alerts)
    print(f"  ✓ Inserted {len(alerts)} flaky alert documents")

    # Summary
    print("\n--- Seed Complete ---")
    print(f"Database : {DB_NAME}")
    print(f"test_runs: {db.test_runs.count_documents({})} documents")
    print(f"flaky_alerts: {db.flaky_alerts.count_documents({})} documents")
    print("\nTop flaky tests detected:")
    for a in alerts[:5]:
        print(f"  [{a['severity'].upper()}] {a['test_name']} — {int(a['flakiness_score']*100)}% failure rate")
        print(f"         Pattern: {a['pattern_notes']}")

    client.close()
    print("\nDone! Your MongoDB database is ready for the agent.")

if __name__ == "__main__":
    main()
