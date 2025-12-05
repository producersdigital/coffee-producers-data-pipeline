from src.utils.file_handler import FileHandler
from src.utils.dni_cleaner import clean_and_validate_dnis

# Read complex multi-sheet file
handler = FileHandler(base_path)
ecol_df = handler.read_excel_with_multirow_header(
    file_path, 'Ecol', header_rows=[7,8,9,10]
)

# Clean DNI in each sheet's data
ecol_df = clean_and_validate_dnis(ecol_df, dni_column='dni')
c2_df = clean_and_validate_dnis(c2_df, dni_column='dni')
# ... etc for each sheet