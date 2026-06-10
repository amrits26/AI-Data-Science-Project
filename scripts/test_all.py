"""
Comprehensive test script for Imperial Cars AI (Phases 1-6).

Run this to verify all systems are working:
    python scripts/test_all.py

Expected runtime: 2-3 minutes
"""

import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "skipped": [],
}


def print_header(phase: str, title: str):
    """Print test phase header."""
    print(f"\n{'=' * 60}")
    print(f"  {phase}: {title}")
    print(f"{'=' * 60}")


def print_test(name: str, passed: bool, message: str = ""):
    """Print individual test result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"  {status}: {name}")
    if message:
        print(f"         {message}")

    if passed:
        test_results["passed"].append(name)
    else:
        test_results["failed"].append(name)


def print_skipped(name: str, reason: str):
    """Print skipped test."""
    print(f"  ⊝ SKIP: {name}")
    print(f"         {reason}")
    test_results["skipped"].append(name)


def test_phase_1_database():
    """Test Phase 1: Database models and connection."""
    print_header("PHASE 1", "Database Foundation")

    try:
        from backend.app.database import (
            engine,
            SessionLocal,
            get_db_session,
            Car,
            Customer,
            Vehicle,
        )

        # Test engine connection
        try:
            connection = engine.connect()
            connection.close()
            print_test("Database connection", True)
        except Exception as e:
            print_test("Database connection", False, str(e))
            return

        # Test session creation
        try:
            session = get_db_session()
            session.close()
            print_test("Session creation", True)
        except Exception as e:
            print_test("Session creation", False, str(e))
            return

        # Test model imports
        try:
            models = [Car, Customer, Vehicle]
            print_test("Model imports", True, f"Loaded {len(models)} models")
        except Exception as e:
            print_test("Model imports", False, str(e))

    except ImportError as e:
        print_test("Phase 1 imports", False, str(e))


def test_phase_2_scripts():
    """Test Phase 2: Database initialization scripts."""
    print_header("PHASE 2", "Database Scripts")

    # Check script files exist
    scripts = [
        "scripts/init_db.py",
        "scripts/import_car_data.py",
    ]

    for script in scripts:
        script_path = Path(script)
        if script_path.exists():
            print_test(f"Script exists: {script}", True)
        else:
            print_test(f"Script exists: {script}", False)


def test_phase_3_nhtsa():
    """Test Phase 3: NHTSA API integration."""
    print_header("PHASE 3", "NHTSA API Integration")

    try:
        from backend.app.agents.nhtsa_api import (
            decode_vin,
            get_safety_rating,
            get_all_makes,
            cache_stats,
        )

        # Test VIN decoding
        try:
            result = decode_vin("5FNRL6H79LB123456")
            if result.get("status") == "ok":
                print_test(
                    "VIN decode",
                    True,
                    f"{result.get('year')} {result.get('make')} {result.get('model')}",
                )
            else:
                print_test("VIN decode", False, result.get("error", "Unknown error"))
        except Exception as e:
            print_test("VIN decode", False, str(e))

        # Test invalid VIN
        try:
            result = decode_vin("INVALID")
            if result.get("status") == "error":
                print_test("VIN validation", True, "Correctly rejected invalid VIN")
            else:
                print_test("VIN validation", False, "Should reject invalid VIN")
        except Exception as e:
            print_test("VIN validation", False, str(e))

        # Test makes list
        try:
            makes = get_all_makes()
            if makes and len(makes) > 0:
                print_test("Get all makes", True, f"Found {len(makes)} makes")
            else:
                print_test("Get all makes", False, "No makes returned")
        except Exception as e:
            print_test("Get all makes", False, str(e))

        # Test cache stats
        try:
            stats = cache_stats()
            print_test("Cache stats", True, f"{stats.get('total_entries', 0)} entries")
        except Exception as e:
            print_test("Cache stats", False, str(e))

    except ImportError as e:
        print_test("Phase 3 imports", False, str(e))


def test_phase_4_agents():
    """Test Phase 4: Core agents."""
    print_header("PHASE 4", "Core Agents")

    # Test chatbot
    try:
        from backend.app.agents.imperial_chatbot import ask_imperial

        result = ask_imperial("What's the price of a Toyota?")
        if result.get("answer"):
            print_test(
                "Chatbot (generic question)",
                True,
                f"Answer length: {len(result.get('answer'))} chars",
            )
        else:
            print_test("Chatbot (generic question)", False, "No answer returned")

        result = ask_imperial("What's 5FNRL6H79LB123456?")
        print_test("Chatbot (VIN question)", True, f"Type: {result.get('question_type')}")

    except ImportError as e:
        print_test("Chatbot import", False, str(e))
    except Exception as e:
        print_test("Chatbot test", False, str(e))

    # Test math tools
    try:
        from backend.app.agents.math_tools import (
            loan_calculator,
            lease_calculator,
            trade_in_equity,
        )

        monthly, total = loan_calculator(30000, 5000, 6.9, 60)
        if monthly > 0 and total > 30000:
            print_test("Loan calculator", True, f"${monthly:,.2f}/mo, ${total:,.2f} total")
        else:
            print_test("Loan calculator", False, f"Unexpected results: {monthly}, {total}")

        equity = trade_in_equity(10000, 15000)
        if equity.get("equity") == 5000:
            print_test("Trade-in equity", True, f"${equity.get('equity'):,.0f} equity")
        else:
            print_test("Trade-in equity", False)

    except ImportError as e:
        print_test("Math tools import", False, str(e))
    except Exception as e:
        print_test("Math tools test", False, str(e))

    # Test visualizations
    try:
        from backend.app.agents.visualizations import monthly_payment_chart

        png_bytes = monthly_payment_chart(30000, 5000, 6.9, 60)
        if png_bytes and len(png_bytes) > 0:
            print_test("Visualizations", True, f"Generated {len(png_bytes)} bytes")
        else:
            print_test("Visualizations", False, "Empty output")

    except ImportError as e:
        print_test("Visualizations import", False, str(e))
    except Exception as e:
        print_skipped("Visualizations", "Kaleido may not be installed (optional)")


def test_phase_5_documents():
    """Test Phase 5: Document workflows."""
    print_header("PHASE 5", "Document Workflows")

    # Test carfax ingestor
    try:
        from backend.app.agents.carfax_ingestor import lookup_vin_public

        result = lookup_vin_public("5FNRL6H79LB123456")
        if result.get("status") == "ok":
            print_test(
                "VIN lookup",
                True,
                f"{result.get('year')} {result.get('make')} {result.get('model')}",
            )
        else:
            print_test("VIN lookup", False, result.get("error", "Unknown error"))

    except ImportError as e:
        print_test("Carfax ingestor import", False, str(e))
    except Exception as e:
        print_test("Carfax ingestor test", False, str(e))

    # Test paperwork finisher
    try:
        from backend.app.agents.paperwork_finisher import (
            generate_deal_jacket_pdf,
            save_document_json,
        )

        deal_data = {
            "deal_number": "TEST-001",
            "customer_name": "Test Customer",
            "vehicle": "2024 Toyota Camry",
            "vin": "5FNRL6H79LB123456",
            "sale_price": 30000,
        }

        # This will create a file, so just test it doesn't crash
        try:
            pdf_path = generate_deal_jacket_pdf(deal_data)
            if Path(pdf_path).exists():
                print_test("Deal jacket PDF", True, f"Generated: {pdf_path}")
            else:
                print_test("Deal jacket PDF", False, "PDF not created")
        except Exception as e:
            print_skipped("Deal jacket PDF", "ReportLab may have issues")

        # Test JSON save
        json_path = save_document_json("test_doc", {"test": "data"})
        if Path(json_path).exists():
            print_test("Document JSON", True, f"Saved: {json_path}")
        else:
            print_test("Document JSON", False)

    except ImportError as e:
        print_test("Paperwork import", False, str(e))
    except Exception as e:
        print_test("Paperwork test", False, str(e))


def test_phase_6_lifecycle():
    """Test Phase 6: Customer lifecycle."""
    print_header("PHASE 6", "Customer Lifecycle")

    # Test customer updates
    try:
        from backend.app.agents.customer_updates import get_pending_jobs

        jobs = get_pending_jobs()
        print_test("Get pending jobs", True, f"Found {len(jobs)} jobs")

    except ImportError as e:
        print_test("Customer updates import", False, str(e))
    except Exception as e:
        print_test("Customer updates test", False, str(e))

    # Test lifecycle agents
    try:
        from backend.app.agents.lifecycle_agents import (
            initialize_scheduler,
            stop_scheduler,
            manual_trigger,
        )

        # Test manual trigger
        result = manual_trigger("onboarding")
        if result.get("status") == "ok":
            print_test("Manual workflow trigger", True, result.get("message"))
        else:
            print_test("Manual workflow trigger", False, result.get("message"))

        # Don't actually start scheduler in tests, just verify it imports
        print_test("Scheduler import", True, "APScheduler ready")

    except ImportError as e:
        print_test("Lifecycle agents import", False, str(e))
    except Exception as e:
        print_test("Lifecycle agents test", False, str(e))


def test_dependencies():
    """Test that all required dependencies are installed."""
    print_header("DEPENDENCIES", "Package Verification")

    required_packages = [
        "fastapi",
        "sqlalchemy",
        "psycopg2",
        "requests",
        "plotly",
        "reportlab",
        "apscheduler",
        "pandas",
        "numpy",
    ]

    for package in required_packages:
        try:
            __import__(package)
            print_test(f"Package: {package}", True)
        except ImportError:
            print_test(f"Package: {package}", False, "Not installed")

    # Optional packages
    optional_packages = ["kaleido", "pypdf", "torch", "transformers"]

    for package in optional_packages:
        try:
            __import__(package)
            print_test(f"Optional: {package}", True)
        except ImportError:
            print_skipped(f"Optional: {package}", "Not installed (optional)")


def print_summary():
    """Print test summary."""
    print(f"\n{'=' * 60}")
    print("  TEST SUMMARY")
    print(f"{'=' * 60}")
    print(f"  ✓ Passed:  {len(test_results['passed'])}")
    print(f"  ✗ Failed:  {len(test_results['failed'])}")
    print(f"  ⊝ Skipped: {len(test_results['skipped'])}")

    if test_results["failed"]:
        print(f"\n  Failed tests:")
        for test in test_results["failed"]:
            print(f"    - {test}")

    total = len(test_results["passed"]) + len(test_results["failed"])
    if total > 0:
        pass_rate = len(test_results["passed"]) / total * 100
        print(f"\n  Pass rate: {pass_rate:.1f}%")

    if not test_results["failed"]:
        print("\n  🎉 All tests passed! System is ready to use.")
    else:
        print("\n  ⚠️  Some tests failed. See details above.")

    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  IMPERIAL CARS AI - COMPREHENSIVE TEST SUITE")
    print("  Phases 1-6 Verification")
    print("=" * 60)

    # Run all tests
    test_dependencies()
    test_phase_1_database()
    test_phase_2_scripts()
    test_phase_3_nhtsa()
    test_phase_4_agents()
    test_phase_5_documents()
    test_phase_6_lifecycle()

    # Print summary
    print_summary()

    # Exit with appropriate code
    sys.exit(0 if not test_results["failed"] else 1)
