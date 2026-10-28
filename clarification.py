"""Conservative output-only question gate; never routes or parses customer input.
A clarification needs no inventory proof. It cannot carry cards or stock claims.
False negatives retain the normal evidence guard and bounded agent correction.
"""
import re,unicodedata

def folded(text):
    # Vietnamese chị (address) must not become chỉ (exclusivity) after folding.
    text=unicodedata.normalize('NFC',text.casefold())
    text=re.sub(r'\bchị\b','__address__',text)
    return ''.join(c for c in unicodedata.normalize('NFD',text.replace('đ','d')) if unicodedata.category(c)!='Mn')

def only_question(text):
    from agent_answer import risky_stock_wording
    from turn_contract import PROTOCOL
    if not isinstance(text,str) or not text.strip() or len(text)>800 or text.count('?')>2:return False
    n=folded(text)
    # Interrogative/request syntax is not evidence: the negative checks below
    # must also pass, including when a fabricated claim is followed by '?'.
    if '?' not in text and not re.search(r'\b(?:cho\b.{0,25}\bbiet|noi ro|lam ro|xac nhan|vui long)\b',n):return False
    if PROTOCOL.search(text) or re.search(r'https?://|www\.|\b(?:ben duoi|cac the|the san pham)\b',n):return False
    if risky_stock_wording(text,{'variants':[]}):return False
    if re.search(r'\d[\d.,]*\s*(?:k\b|đ(?:ồng)?\b|₫|vnd\b)',text,re.I):return False
    if re.search(r'\b(?:con hang|het hang|co san|san hang|san kho|trong kho|ton kho|in stock|sold out|out of stock|available|availability|stock)\b',n):return False
    if re.search(r'\b(?:con|het|du)\s+(?:size|mau|hang)|\b(?:hien|van|dang)\s+con\b|\b(?:con|co)\s+\d+\s*(?:doi|mau|san pham|sku|chiec)\b',n):return False
    return True
