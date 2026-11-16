"""Filtering and Excel exports for the two activity lists."""
from datetime import date, datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

LOAN_COLUMNS = [
    ("device_name", "設備", "Equipment", 26),
    ("project_name", "專案名稱", "Project", 22),
    ("mitac_pn", "Mitac P/N", "Mitac P/N", 22),
    ("serial_number", "序號 (SN)", "Serial number", 24),
    ("status", "狀態", "Status", 16),
    ("location", "存放位置", "Location", 22),
    ("borrower", "借用人", "Borrower", 20),
    ("borrower_email", "借用人信箱", "Borrower email", 34),
    ("borrow_date", "借出日期", "Borrow date", 18),
    ("expected_return_date", "預計歸還日期", "Expected return", 20),
    ("actual_return_date", "實際歸還日期", "Actual return", 20),
    ("note", "備註", "Note", 50),
]
RECORD_COLUMNS = [
    ("timestamp", "異動時間", "Timestamp", 24),
    ("item_name", "設備名稱", "Equipment", 26),
    ("action_type", "動作類型", "Action", 20),
    ("quantity", "異動數量", "Quantity change", 16),
    ("box_name", "所屬箱子", "Box", 24),
    ("mitac_pn", "Mitac PN", "Mitac PN", 22),
    ("operator", "操作人員", "Operator", 24),
    ("note", "備註", "Note", 50),
]


def matches_loan(loan, parameters, today):
    status = parameters.get("status", "ALL")
    overdue = (
        loan.status == "已借出"
        and bool(loan.expected_return_date)
        and loan.expected_return_date < today
    )
    if status == "OVERDUE":
        if not overdue:
            return False
    elif status != "ALL" and loan.status != status:
        return False
    if parameters.get("project") and loan.project_name != parameters["project"]:
        return False
    text = " ".join(str(getattr(loan, name) or "") for name, *_ in LOAN_COLUMNS)
    return parameters.get("q", "").strip().lower() in text.lower()


def matches_record(record, parameters):
    action = parameters.get("action", "ALL")
    if action != "ALL" and record.action_type != action:
        return False
    values = [getattr(record, name) for name, *_ in RECORD_COLUMNS]
    values[3] = -abs(record.quantity) if record.action_type == "領出" else record.quantity
    text = " ".join(str(value) if value is not None else "" for value in values)
    return parameters.get("q", "").strip().lower() in text.lower()


def excel_date(value):
    """Keep older non-ISO values available as text."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return value


def create_workbook(title, columns, rows, language="zh"):
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(title)
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = "A2"
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    body_font = Font(name="Calibri", size=11, color="172B3E")
    header_fill = PatternFill("solid", fgColor="152C40")
    stripe = PatternFill("solid", fgColor="F2F5F7")
    alignment = Alignment(vertical="top", wrap_text=True)
    for index, column in enumerate(columns, 1):
        sheet.column_dimensions[get_column_letter(index)].width = column[3]
    header = []
    for column in columns:
        cell = WriteOnlyCell(sheet, column[2] if language == "en" else column[1])
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = alignment
        header.append(cell)
    sheet.append(header)
    row_number = 1
    for row_number, values in enumerate(rows, 2):
        row = []
        for value in values:
            if isinstance(value, str):
                value = ILLEGAL_CHARACTERS_RE.sub("", value)
            cell = WriteOnlyCell(sheet, value)
            # Export user-supplied text literally, including leading "=" and zeroes.
            if isinstance(value, str):
                cell.data_type = "s"
                cell.number_format = "@"
            elif isinstance(value, datetime):
                cell.number_format = "yyyy-mm-dd hh:mm:ss"
            elif isinstance(value, date):
                cell.number_format = "yyyy-mm-dd"
            elif isinstance(value, (int, float)):
                cell.number_format = "0"
            cell.font = body_font
            cell.alignment = alignment
            if row_number % 2 == 0:
                cell.fill = stripe
            row.append(cell)
        sheet.append(row)
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{row_number}"
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
