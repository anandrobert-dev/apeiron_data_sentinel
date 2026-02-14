
import polars as pl
import xlsxwriter

df = pl.DataFrame({
    "invoice_number": ["INV001", "INV002", "INV001", "INV003"],
    "carrier_code": ["UPS", "FedEx", "UPS", "DHL"],
    "amount": [100.0, 200.0, 100.0, 300.0],
    "date": ["2023-01-01", "2023-01-02", "2023-01-01", "2023-01-03"]
})

df.write_excel("test_data.xlsx")
print("test_data.xlsx created successfully.")
