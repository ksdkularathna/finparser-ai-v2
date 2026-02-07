# main.py - Standalone Bank Statement Converter
# Run with: py -m uvicorn main:app --port 8000
# Deploy to Vercel: vercel --prod

import pdfplumber
import pandas as pd
import re
import shutil
import os
import tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from typing import List, Dict, Any

# --- CORE LOGIC (Service Layer) ---

def parse_currency(amount_str: str) -> float:
    """
    Cleans currency strings like '$1,234.56', '(50.00)', '50.00 CR' 
    into float values.
    """
    if not amount_str:
        return 0.0
    
    # Remove currency symbols, commas, and whitespace
    clean_str = str(amount_str).replace('$', '').replace(',', '').strip()
    
    # Handle negative numbers in parenthesis e.g., (50.00)
    is_negative = False
    if '(' in clean_str and ')' in clean_str:
        is_negative = True
        clean_str = clean_str.replace('(', '').replace(')', '')
    
    # Remove any remaining non-numeric chars except decimal point and minus
    clean_str = re.sub(r'[^\d.\-]', '', clean_str)
        
    try:
        value = float(clean_str)
        return -value if is_negative else value
    except ValueError:
        return 0.0


def extract_statement_data(pdf_path: str) -> tuple:
    """
    Main extraction function - uses text-based parsing for better accuracy.
    """
    header_data = {
        "account_number": "Unknown",
        "statement_period": "Unknown",
        "beginning_balance": "Unknown",
        "ending_balance": "Unknown",
    }
    
    transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
        
        # --- Extract Header Information ---
        
        # Account number
        acc_match = re.search(r"Account\s*#\s*(\d+)", full_text)
        if acc_match:
            header_data["account_number"] = acc_match.group(1)
        
        # Beginning balance
        begin_match = re.search(r"Beginning Balance[^\$]*\$([\d,]+\.?\d*)", full_text)
        if begin_match:
            header_data["beginning_balance"] = "$" + begin_match.group(1)
        
        # Ending balance
        end_match = re.search(r"Ending Balance[^\$]*\$([\d,]+\.?\d*)", full_text)
        if end_match:
            header_data["ending_balance"] = "$" + end_match.group(1)
        
        # Statement period
        period_match = re.search(r"(?:Beginning Balance on|from)\s+([A-Za-z]+\s+\d+,?\s+\d{4})", full_text)
        end_period = re.search(r"(?:Ending Balance on|through|to)\s+([A-Za-z]+\s+\d+,?\s+\d{4})", full_text)
        if period_match and end_period:
            header_data["statement_period"] = f"{period_match.group(1)} - {end_period.group(1)}"
        
        # --- Extract Transactions ---
        
        # Pattern 1: Deposits - "Description Date Amount" format
        # Example: "Deposit Ref Nbr: 130012345 05-15 $3,615.08"
        deposit_pattern = r"(Deposit[^\n]*?)\s+(\d{2}-\d{2})\s+\$([\d,]+\.?\d*)"
        for match in re.finditer(deposit_pattern, full_text):
            transactions.append({
                "Date": match.group(2),
                "Description": match.group(1).strip(),
                "Type": "Credit",
                "Amount": parse_currency(match.group(3))
            })
        
        # Pattern 2: ATM Withdrawals - multi-line format
        # Format: "ATM Withdrawal\nLocation\nCity State ID MM-DD MM-DD $Amount"
        atm_section = re.search(r"ATM Withdrawals \& Debits Account.*?\n(.*?)(?=Total ATM|$)", full_text, re.DOTALL)
        if atm_section:
            atm_text = atm_section.group(1)
            # Match the pattern with dates and amount at end of multi-line block
            atm_pattern = r"ATM Withdrawal\n([^\n]+)\n([^\n]*?)(\d{2}-\d{2})\s+(\d{2}-\d{2})\s+\$([\d,]+\.?\d*)"
            for match in re.finditer(atm_pattern, atm_text, re.DOTALL):
                location = match.group(1).strip()
                transactions.append({
                    "Date": match.group(4),  # Use "Date Paid" column
                    "Description": f"ATM Withdrawal - {location}",
                    "Type": "Debit",
                    "Amount": parse_currency(match.group(5))
                })
        
        # Pattern 3: Checks Paid - "Date Check# Amount Reference" format
        # Example: "05-12 1001 75.00 00012576589"
        checks_section = re.search(r"ChecksPaid[^\n]*\n.*?Date Paid[^\n]*\n(.*?)(?=Total Checks|$)", full_text, re.DOTALL)
        if checks_section:
            checks_text = checks_section.group(1)
            check_pattern = r"(\d{2}-\d{2})\s+(\d+)\s+([\d,]+\.?\d*)\s+(\d+)"
            for match in re.finditer(check_pattern, checks_text):
                transactions.append({
                    "Date": match.group(1),
                    "Description": f"Check #{match.group(2)}",
                    "Type": "Debit",
                    "Amount": parse_currency(match.group(3))
                })
        
        # Pattern 4: Generic line-based extraction as fallback
        # Look for lines with date pattern followed by amount
        if not transactions:
            # Fallback: find any line with MM-DD date and dollar amount
            generic_pattern = r"(\d{2}-\d{2})\s+(.*?)\s+\$([\d,]+\.?\d*)"
            for match in re.finditer(generic_pattern, full_text):
                transactions.append({
                    "Date": match.group(1),
                    "Description": match.group(2).strip()[:50],
                    "Type": "Unknown",
                    "Amount": parse_currency(match.group(3))
                })

    # Create DataFrame
    if transactions:
        df = pd.DataFrame(transactions)
        # Sort by date
        df = df.sort_values('Date').reset_index(drop=True)
    else:
        df = pd.DataFrame(columns=["Date", "Description", "Type", "Amount"])
    
    return header_data, df


def generate_excel(header_data: Dict[str, Any], df: pd.DataFrame, output_path: str) -> None:
    """
    Writes data to Excel with formatting.
    """
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # Formats
        header_format = workbook.add_format({
            'bold': True, 'bg_color': '#1e3a5f', 'font_color': 'white',
            'border': 1, 'align': 'center'
        })
        money_format = workbook.add_format({'num_format': '$#,##0.00', 'border': 1})
        cell_format = workbook.add_format({'border': 1})
        
        # Sheet 1: Summary
        summary_df = pd.DataFrame(list(header_data.items()), columns=['Field', 'Value'])
        summary_df.to_excel(writer, sheet_name='Summary', index=False, startrow=1, header=False)
        
        summary_sheet = writer.sheets['Summary']
        summary_sheet.write_row('A1', ['Field', 'Value'], header_format)
        summary_sheet.set_column('A:A', 20)
        summary_sheet.set_column('B:B', 30)
        
        # Sheet 2: Transactions
        if not df.empty:
            df.to_excel(writer, sheet_name='Transactions', index=False, startrow=1, header=False)
            
            trans_sheet = writer.sheets['Transactions']
            for col_num, column in enumerate(df.columns):
                trans_sheet.write(0, col_num, column, header_format)
            
            # Format Amount column
            amount_col = df.columns.get_loc('Amount') if 'Amount' in df.columns else -1
            if amount_col >= 0:
                for row in range(len(df)):
                    trans_sheet.write(row + 1, amount_col, df.iloc[row]['Amount'], money_format)
            
            # Set column widths
            trans_sheet.set_column('A:A', 12)  # Date
            trans_sheet.set_column('B:B', 40)  # Description
            trans_sheet.set_column('C:C', 10)  # Type
            trans_sheet.set_column('D:D', 15)  # Amount


# --- API LAYER (FastAPI) ---

app = FastAPI(title="Bank Statement Converter")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

# Use system temp directory (works on Vercel's read-only filesystem)
TEMP_DIR = Path(tempfile.gettempdir())


@app.post("/convert")
async def convert_statement(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PDF.")

    temp_pdf = TEMP_DIR / f"temp_{file.filename}"
    output_xlsx = TEMP_DIR / f"converted_{os.path.splitext(file.filename)[0]}.xlsx"
    
    try:
        with open(temp_pdf, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        header, df = extract_statement_data(str(temp_pdf))
        
        if df.empty:
            raise HTTPException(status_code=422, detail="Could not extract any transactions. The PDF format might not be supported.")
        
        generate_excel(header, df, str(output_xlsx))
        
        return FileResponse(
            output_xlsx, 
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
            filename=output_xlsx.name
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        if temp_pdf.exists():
            os.remove(temp_pdf)


# Serve static files
@app.get("/assets/{file_path:path}")
async def serve_assets(file_path: str):
    """Serve static assets (JS, CSS)"""
    asset_path = STATIC_DIR / "assets" / file_path
    if asset_path.exists() and asset_path.is_file():
        return FileResponse(asset_path)
    raise HTTPException(status_code=404, detail="Asset not found")

@app.get("/{file_name:path}")
async def serve_static(file_name: str):
    """Serve index.html and other static files"""
    if not file_name or file_name == "/":
        file_name = "index.html"
    
    file_path = STATIC_DIR / file_name
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    # For SPA routing, return index.html
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    
    raise HTTPException(status_code=404, detail="Not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
