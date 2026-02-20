"""
Transactions Cleaners Package

Contains cleaner classes for processing transaction data (acopio files)
from different Producer Organizations.

Transaction data is typically simpler than inspection data:
- Single-row headers
- Fewer columns
- Standard format across years
"""

from .bagua_transactions_cleaner import BaguaTransactionsCleaner, clean_bagua_transactions

__all__ = [
    'BaguaTransactionsCleaner',
    'clean_bagua_transactions',
    # Future cleaners will be added here:
    # 'HuadquinaTransactionsCleaner',
    # 'ChirinosTransactionsCleaner',
    # etc.
]