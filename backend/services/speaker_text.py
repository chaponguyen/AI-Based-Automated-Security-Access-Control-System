# Agent 2 — Xử lý văn bản tiếng Việt cho loa thông báo (B14)
# docs/context/API_CONTRACT.md và docs/plan/MO_TA_CONG_VIEC.md mục B14

DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def _doc_hai_chu_so(n: int) -> str:
    """Đổi số từ 0 đến 99 thành chữ tiếng Việt theo ngữ pháp chuẩn (CP-02)."""
    if n < 0 or n > 99:
        raise ValueError(f"Số ngoài khoảng 0-99: {n}")
    if n < 10:
        return DIGITS[n]
    if n == 10:
        return "mười"
    if n < 20:
        unit = n % 10
        if unit == 5:
            return "mười lăm"
        return f"mười {DIGITS[unit]}"

    chuc = n // 10
    unit = n % 10
    chuc_str = f"{DIGITS[chuc]} mươi"
    if unit == 0:
        return chuc_str
    if unit == 1:
        return f"{chuc_str} mốt"
    if unit == 5:
        return f"{chuc_str} lăm"
    return f"{chuc_str} {DIGITS[unit]}"


def so_sang_chu(n: int) -> str:
    """Đổi số nguyên từ 0 đến 999 thành chữ tiếng Việt chuẩn (CP-02).
    
    Quy tắc:
    - 0: 'không'
    - 5 sau hàng chục: 'lăm' (15 -> 'mười lăm', 25 -> 'hai mươi lăm')
    - 1 sau hàng chục từ 20 trở lên: 'mốt' (21 -> 'hai mươi mốt', 41 -> 'bốn mươi mốt')
    - 10: 'mười', 11-19: 'mười một' ... 'mười lăm'
    - Hàng trăm: 'trăm', hàng chục bằng 0 đọc là 'linh' (105 -> 'một trăm linh năm').
    """
    if not isinstance(n, int):
        raise TypeError(f"Giá trị phải là số nguyên, nhận được {type(n)}")
    if n < 0 or n > 999:
        raise ValueError(f"Hỗ trợ số từ 0 đến 999, nhận được {n}")

    if n < 100:
        return _doc_hai_chu_so(n)

    tram = n // 100
    du = n % 100
    tram_str = f"{DIGITS[tram]} trăm"
    if du == 0:
        return tram_str
    if du < 10:
        unit_str = "năm" if du == 5 else DIGITS[du]
        return f"{tram_str} linh {unit_str}"
    return f"{tram_str} {_doc_hai_chu_so(du)}"


def doc_gio(dt) -> str:
    """Đổi giờ và phút từ đối tượng datetime sang câu chữ tiếng Việt tự nhiên (CP-03).

    Quy tắc:
    - Giờ 24h: 0 đến 23 qua so_sang_chu.
    - Giờ 0 đọc là 'không giờ'.
    - Phút = 0: đọc 'đúng' (ví dụ: 'không giờ đúng', 'chín giờ đúng').
    - Phút 1 đến 9: đọc 'linh' (ví dụ: 'chín giờ linh năm phút', 'mười hai giờ linh năm phút').
    - Phút >= 10: đọc '{số} phút' (ví dụ: 'chín giờ ba mươi lăm phút', 'hai mươi ba giờ năm mươi chín phút').
    """
    gio_str = so_sang_chu(dt.hour)
    if dt.minute == 0:
        return f"{gio_str} giờ đúng"

    if 1 <= dt.minute <= 9:
        unit_str = "năm" if dt.minute == 5 else DIGITS[dt.minute]
        return f"{gio_str} giờ linh {unit_str} phút"

    phut_str = so_sang_chu(dt.minute)
    return f"{gio_str} giờ {phut_str} phút"

