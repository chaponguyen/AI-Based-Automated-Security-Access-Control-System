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


BANG_CHU_CAI = {
    "A": "a", "B": "bê", "C": "xê", "D": "đê", "E": "e", "F": "ép",
    "G": "gờ", "H": "hắt", "I": "i", "J": "giê", "K": "ca", "L": "e-lờ",
    "M": "em", "N": "en", "O": "o", "P": "pê", "Q": "quy", "R": "e-rờ",
    "S": "ét", "T": "tê", "U": "u", "V": "vê", "W": "vê-đúp", "X": "ích",
    "Y": "i-dài", "Z": "dét",
}


def doc_can_ho(code: str, mode: str = None) -> str:
    """Đổi mã căn hộ sang chuỗi tiếng Việt phát âm rõ ràng cho loa (CP-04).

    Quy tắc:
    - Chữ cái khối nhà: đọc theo bảng chữ cái tiếng Việt (A->a, B->bê, C->xê...).
    - Dấu '-', '/', '.' được loại bỏ.
    - Số phòng theo mode:
      + 'floor_room' (mặc định): 2 chữ số cuối là phòng (dưới 10 đọc kèm 'không'),
        các số trước là tầng (ví dụ: A-1203 -> 'a, mười hai không ba', B-0807 -> 'bê, tám không bảy',
        C-502 -> 'xê, năm không hai', A-1205 -> 'a, mười hai không năm').
      + 'digits': đọc từng chữ số (ví dụ: 'một hai không ba').
    """
    if not code:
        return ""

    import os
    import re

    if mode is None:
        mode = os.getenv("ROOM_READ_MODE", "floor_room")

    code_str = str(code).strip()
    m = re.search(r"([a-zA-Z]+)?(?:[^0-9a-zA-Z]*)([0-9]+)?", code_str)
    letters = m.group(1) if m else None
    digits = m.group(2) if m else None

    letter_text = ""
    if letters:
        letter_text = ", ".join(BANG_CHU_CAI.get(c.upper(), c.lower()) for c in letters)

    num_text = ""
    if digits:
        if mode == "digits":
            num_text = " ".join(DIGITS[int(d)] for d in digits)
        else:  # floor_room
            if len(digits) >= 3:
                tang_num = int(digits[:-2])
                phong_str = digits[-2:]
                phong_num = int(phong_str)
                tang_text = so_sang_chu(tang_num)
                if phong_num < 10:
                    phong_text = f"không {DIGITS[phong_num]}"
                else:
                    phong_text = so_sang_chu(phong_num)
                num_text = f"{tang_text} {phong_text}"
            else:
                num_text = so_sang_chu(int(digits))

    if letter_text and num_text:
        return f"{letter_text}, {num_text}"
    if letter_text:
        return letter_text
    if num_text:
        return num_text
    return re.sub(r"[-/.]", " ", code_str).strip()


def doc_ten(name: str) -> str:
    """Chuẩn hóa tên cư dân để loa đọc liền mạch, không đánh vần (CP-04).

    Quy tắc:
    - Bỏ chữ số, ký tự đặc biệt, dấu câu lạ.
    - Giữ nguyên chữ có dấu tiếng Việt.
    - Chuyển TOÀN CHỮ HOA thành Title Case để engine TTS không đánh vần từng chữ cái.
    """
    if not name:
        return ""

    import re

    name_str = str(name).strip()
    if name_str.isupper():
        name_str = name_str.title()

    clean_name = re.sub(
        r"[^a-zA-ZàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệđìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẸÊỀẾỂỄỆĐÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ\s]",
        "",
        name_str,
    )
    return " ".join(clean_name.split())


