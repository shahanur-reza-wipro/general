#!/usr/bin/env python
"""
Simplified data ingestion test script
Tests database connectivity and basic data operations
"""
import os
import sys

# Configure environment
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Test database connection and basic operations
from data_access_layer.database import Database
from data_access_layer.models import Debtor, Transaction, RunControl
from repositories import DebtorRepository, TransactionRepository

print("=" * 60)
print("DATA INGESTION TEST - PostgreSQL Database Connection")
print("=" * 60)

try:
    # 1. Database Connection Test
    print("\n1. Testing database connection...")
    db = Database()
    print("   ✓ Database initialized successfully")
    
    # 2. Check database schema
    print("\n2. Checking database schema...")
    inspector = db.get_inspector()
    tables = inspector.get_table_names()
    print(f"   ✓ Found {len(tables)} tables in database:")
    for table in sorted(tables):
        print(f"     - {table}")
    
    # 3. Query sample data
    print("\n3. Querying sample data...")
    debtor_count = db.get_count(Debtor)
    transaction_count = db.get_count(Transaction)
    run_control_count = db.get_count(RunControl)
    print(f"   ✓ Debtors: {debtor_count}")
    print(f"   ✓ Transactions: {transaction_count}")
    print(f"   ✓ Run Controls: {run_control_count}")
    
    # 4. Test data layer repositories
    print("\n4. Testing repositories...")
    debtor_repo = DebtorRepository()
    print("   ✓ DebtorRepository instantiated")
    
    transaction_repo = TransactionRepository()
    print("   ✓ TransactionRepository instantiated")
    
    # 5. Extract files info
    print("\n5. Extract files found:")
    extract_dir = "../extract_files"
    if os.path.isdir(extract_dir):
        files = os.listdir(extract_dir)
        for file in files:
            file_path = os.path.join(extract_dir, file)
            file_size = os.path.getsize(file_path)
            print(f"   ✓ {file} ({file_size:,} bytes)")
    
    print("\n" + "=" * 60)
    print("✓ DATA INGESTION TEST PASSED")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run FileValidationService to validate files")
    print("2. Run DebtorService to ingest debtor records")
    print("3. Run TransactionService to ingest transaction records")
    print("4. Query database to verify data ingestion")
    
except Exception as e:
    print(f"\n✗ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
