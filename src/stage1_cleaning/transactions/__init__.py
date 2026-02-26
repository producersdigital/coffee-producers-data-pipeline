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
from .huadquina_transactions_cleaner import HuadquinaTransactionsCleaner

__all__ = [
    'BaguaTransactionsCleaner',
    'clean_bagua_transactions',
    'HuadquinaTransactionsCleaner'
    # Future cleaners will be added here:
    # 'HuadquinaTransactionsCleaner',
    # 'ChirinosTransactionsCleaner',
    # etc.
]