#!/usr/bin/env python
"""
End-to-end data ingestion test with error handling
"""
import os
import sys
import time

# Configure environment
os.chdir(os.path.dirname(os.path.abspath(__file__)))
start_time = time.time()

print("=" * 70)
print("DATA INGESTION TEST - END-TO-END")
print("=" * 70)

try:
    # 1. Initialize configuration
    print("\n[1] Loading configuration...")
    from utilities.coniguration import Configuration
    config = Configuration()
    config_data = config.get_config()
    print(f"    ✓ Environment: {config_data.env}")
    print(f"    ✓ Local Mode: {config_data.isLocal}")
    print(f"    ✓ Database: {config_data.dbHost}:{config_data.dbPort}/{config_data.dbName}")
    
    # 2. Initialize database
    print("\n[2] Initializing database...")
    from data_access_layer.database import Database
    db = Database()
    print(f"    ✓ Database connection established")
    
    # 3. Reset and create tables
    print("\n[3] Resetting database schema...")
    db.reset_database()
    db.create_tables()
    print(f"    ✓ Tables created successfully")
    
    # 4. Check database contents
    print("\n[4] Checking database contents...")
    from data_access_layer.models import Debtor, Transaction, RunControl
    debtor_count = db.get_count(Debtor)
    transaction_count = db.get_count(Transaction)
    run_control_count = db.get_count(RunControl)
    print(f"    ✓ Debtors: {debtor_count}")
    print(f"    ✓ Transactions: {transaction_count}")
    print(f"    ✓ Run Controls: {run_control_count}")
    
    # 5. Test data ingestion services
    print("\n[5] Testing Debtor Service...")
    from services import DebtorService
    debtor_service = DebtorService()
    print(f"    ✓ DebtorService instantiated")
    
    print("\n[6] Testing Transaction Service...")
    from services import TransactionService
    transaction_service = TransactionService()
    print(f"    ✓ TransactionService instantiated")
    
    # 6. Process extract files
    print("\n[7] Processing extract files...")
    debtor_file_path = os.path.join(os.path.dirname(__file__), "../extract_files/ABC12933EE.dat")
    transaction_file_path = os.path.join(os.path.dirname(__file__), "../extract_files/BDISTMOUT320250325164002.txt")
    
    if os.path.exists(debtor_file_path):
        print(f"    • Processing debtor file: {os.path.basename(debtor_file_path)}")
        with open(debtor_file_path, "r") as file:
            debtors = debtor_service.process_debtors(file, os.path.basename(debtor_file_path))
        debtor_count_after = db.get_count(Debtor)
        print(f"      ✓ Debtors ingested: {debtor_count_after - debtor_count}")
    else:
        print(f"    ✗ Debtor file not found: {debtor_file_path}")
    
    if os.path.exists(transaction_file_path):
        print(f"    • Processing transaction file: {os.path.basename(transaction_file_path)}")
        with open(transaction_file_path, "r") as file:
            transactions = transaction_service.process_transactions(file, os.path.basename(transaction_file_path))
        transaction_count_after = db.get_count(Transaction)
        print(f"      ✓ Transactions ingested: {transaction_count_after - transaction_count}")
    else:
        print(f"    ✗ Transaction file not found: {transaction_file_path}")
    
    # 7. Final results
    print("\n[8] Final database contents:")
    final_debtor_count = db.get_count(Debtor)
    final_transaction_count = db.get_count(Transaction)
    print(f"    ✓ Total Debtors: {final_debtor_count}")
    print(f"    ✓ Total Transactions: {final_transaction_count}")
    
    execution_time = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"✓ DATA INGESTION TEST COMPLETED SUCCESSFULLY")
    print(f"  Execution time: {execution_time:.2f} seconds")
    print("=" * 70)
    
except Exception as e:
    print(f"\n✗ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
    execution_time = time.time() - start_time
    print(f"\n  Failed after {execution_time:.2f} seconds")
    sys.exit(1)
