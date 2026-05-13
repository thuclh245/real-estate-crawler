import re


FLAGS = re.IGNORECASE | re.MULTILINE
RAW_FLAGS = re.IGNORECASE | re.MULTILINE | re.UNICODE


FEATURE_PATTERNS = {
    "legal_status": {
        "keywords": re.compile(
            r"\b(phap ly|so do|so hong|so rieng|so chung|da co so|"
            r"hop dong mua ban|hdmb|giay to hop le|chua co so|vi bang|"
            r"giay tay|cong chung|sang ten|quy hoach|tranh chap)\b",
            FLAGS,
        ),
        "red_pink_book": re.compile(r"\b(so do|so hong|so rieng)\b", FLAGS),
    },
    "floor_count": {
        "tret_lau": re.compile(r"\b\d+\s*tret\s+(\d{1,2})\s*lau\b", FLAGS),
        "standard": re.compile(
            r"\b(?:so tang|xay dung|ket cau|nha)?\s*[:\-]?\s*(\d{1,2})\s*(?:tang|lau)\b|"
            r"\b(\d{1,2})\s*t\b",
            FLAGS,
        ),
    },
    "seller_type": {
        "owner_negation": re.compile(
            r"\b(khong tiep moi gioi|khong tiep mg|mien moi gioi|khong qua moi gioi)\b",
            FLAGS,
        ),
        "owner": re.compile(
            r"\b(chinh chu|chu nha|chu can ban|chu gui|ban truc tiep|"
            r"mien moi gioi|khong qua moi gioi|khong tiep mg)\b",
            FLAGS,
        ),
        "broker": re.compile(
            r"\b(moi gioi|mg|sale|nhan ky gui|van phong nha dat|cong ty bds)\b",
            FLAGS,
        ),
    },
    "furniture": {
        "full": re.compile(
            r"\b(full noi that|full do|noi that day du|day du noi that|"
            r"noi that cao cap|noi that dep|noi that xin|de lai toan bo noi that|"
            r"du do vao o ngay)\b",
            FLAGS,
        ),
        "basic": re.compile(
            r"\b(noi that co ban|do co ban|ban giao co ban|ban giao hoan thien|"
            r"hoan thien co ban)\b",
            FLAGS,
        ),
        "raw": re.compile(
            r"\b(nha tho|ban giao tho|tho hoan thien|can tho|chua co noi that)\b",
            FLAGS,
        ),
        "mentioned": re.compile(
            r"\b(dieu hoa|nong lanh|tu bep|giuong|sofa|tivi|tu lanh|"
            r"may giat|bep tu|noi that)\b",
            FLAGS,
        ),
    },
    "frontage_width": {
        "patterns": [
            re.compile(
                r"\b(?:mat tien|mt|nong|chieu ngang|ngang)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*m(?![23])\b",
                FLAGS,
            ),
            re.compile(
                r"\b(\d+(?:[.,]\d+)?)\s*m(?![23])\s*(?:mat tien|ngang)\b",
                FLAGS,
            ),
        ]
    },
    "bathroom_count": {
        "patterns": [
            re.compile(r"\b(\d{1,2})\s*(?:phong tam|wc|vs|ve sinh|nha ve sinh|toilet)\b", FLAGS),
            re.compile(r"\b(?:wc|vs|ve sinh|so phong tam)\s*[:\-]?\s*(\d{1,2})\b", FLAGS),
        ]
    },
    "project_name": {
        "patterns": [
            re.compile(r"\b(?:du an|dự án|chung cu|chung cư|khu do thi|khu đô thị)\s+([^.,;\n\r\-]{1,120})", RAW_FLAGS),
        ]
    },
    "bedroom_count": {
        "patterns": [
            re.compile(r"\b(\d{1,2})\s*(?:phong ngu|pn|ngu)\b", FLAGS),
            re.compile(r"\bso phong ngu\s*[:\-]?\s*(\d{1,2})\b", FLAGS),
            re.compile(r"\b(\d{1,2})n(?:\d{1,2}(?:k|vs|wc))?\b", FLAGS),
        ]
    },
    "business": {
        "keywords": re.compile(
            r"\b(kinh doanh|kd|mat pho|mat duong|mat tien kinh doanh|"
            r"vua o vua kinh doanh|buon ban|mo cua hang|mo van phong|"
            r"cho thue kinh doanh|dong tien|shophouse|nha pho thuong mai|"
            r"shop|spa|cafe|nha hang|mat bang|van phong)\b",
            FLAGS,
        )
    },
    "location_context": {
        "urban": re.compile(r"\b(kdt|khu do thi|khu do thi moi|urban|city|residence|garden|park)\b", FLAGS),
        "residential": re.compile(r"\b(khu dan cu|kdc|dan cu dong duc|dong dan cu|khu dan sinh)\b", FLAGS),
        "security": re.compile(r"\b(an ninh|an ninh tot|bao ve 24/7|camera|khu an ninh)\b", FLAGS),
        "educated": re.compile(r"\b(dan tri cao|hang xom van minh|cong dong van minh)\b", FLAGS),
        "subdivision": re.compile(r"\b(phan lo|khu phan lo|dat phan lo|biet thu phan lo)\b", FLAGS),
    },
    "direction": {
        "pattern": re.compile(
            r"\b(?:huong nha|nha huong|dat huong|huong)\s*[:\-]?\s*"
            r"(dong nam|tay bac|dong bac|tay nam|dong|tay|nam|bac|dn|tb|db|tn)\b",
            FLAGS,
        )
    },
    "negotiable_price": {
        "keywords": re.compile(
            r"\b(thuong luong|co thuong luong|gia thuong luong|thoa thuan|"
            r"gia thoa thuan|co tl|tl manh|bot loc|gia chao|"
            r"gia tot cho khach thien chi|khach thien chi co thuong luong)\b",
            FLAGS,
        ),
        "negation_window": re.compile(r"\b(khong|chua|khong co)(?:\s+\w+){0,2}\s+$", FLAGS),
    },
    "car_access": {
        "enter": re.compile(r"\b(o to vao|oto vao|xe hoi vao|oto vao nha|o to vao nha)\b", FLAGS),
        "park": re.compile(
            r"\b(o to do|oto do|o to do cua|oto do cua|cho de o to|bai do xe|"
            r"gara|garage|o to ngu trong nha|oto ngu trong nha)\b",
            FLAGS,
        ),
        "pass": re.compile(
            r"\b(o to tranh|oto tranh|duong o to|duong oto|ngo o to|ngo oto|hem xe hoi)\b",
            FLAGS,
        ),
    },
    "building_name": {
        "pattern": re.compile(
            r"\b(?:toa|tòa|toà|thap|tháp|block|tower)\s+([A-Za-zÀ-ỹ0-9][A-Za-zÀ-ỹ0-9.\-\s]{0,49})",
            RAW_FLAGS,
        )
    },
}
