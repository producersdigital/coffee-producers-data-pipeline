from src.utils.file_handler import FileHandler
from src.utils.dni_cleaner import clean_and_validate_dnis

# Read simpler transaction file
handler = FileHandler(base_path)
trans_df = handler.read_excel_simple(file_path, sheet_name='Acopio')

# Clean DNI column
trans_df = clean_and_validate_dnis(trans_df, dni_column='dni')