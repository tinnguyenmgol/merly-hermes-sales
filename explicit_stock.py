"""Narrow literal stock-query shortcut, NOT a general conversation router.
Only a complete, single explicit model+size and allowlisted stock question.
No SKU normalization, size inference, color merging, history guessing or model.
"""
import re,unicodedata
_LABEL=r'(?:mẫu|mau|mã\s+mẫu|ma\s+mau|mã|ma|sku)(?=\s|[:#]|[0-9])\s*[:#]?\s*'
_CODE=r'(?P<model>[A-Za-z0-9][A-Za-z0-9._-]{0,31})'
_SIZE=r'(?P<size>3[5-9]|4[0-3])'
_PATTERNS=[
    re.compile(r'^'+_LABEL+_CODE+r'\s+(?:size\s*[:#]?\s*)?'+_SIZE+r'\s+(?P<question>.+)$',re.I),
    re.compile(r'^'+_LABEL+_CODE+r'\s+(?:còn|con)\s+(?:size\s*)?'+_SIZE+r'\s+(?P<question>.+)$',re.I),
]
_QUESTIONS={'con mau gi','con mau nao','con nhung mau nao','con mau gi khong','con mau gi ko','con khong','con ko','con k','con hang khong','con hang ko','co hang khong','co khong','co ko','ton kho','kiem tra ton','kiem tra ton kho'}
def parse(message):
    if not isinstance(message,str) or not 1<=len(message)<=200:return None
    text=message.strip()
    for index,pattern in enumerate(_PATTERNS):
        match=pattern.fullmatch(text)
        if not match:continue
        code=match.group('model')
        if re.fullmatch(r'[0-9]+(?:[.,][0-9]+)?(?:cm|mm|m|inch|in|kg|g|phan)',code,re.I) and not re.match(r'^(?:sku|mã|ma)\b',text,re.I):return None
        question=match.group('question').casefold().replace('đ','d')
        question=''.join(ch for ch in unicodedata.normalize('NFD',question) if unicodedata.category(ch)!='Mn')
        question=re.sub(r'[?!.]+',' ',question)
        question=' '.join(question.split())
        for _ in range(2):question=re.sub(r'\s+(?:a|nha|nhe|giup toi|giup minh)$','',question)
        if index==1:question='con '+question
        if question not in _QUESTIONS:return None
        return {'model_code':match.group('model'),'size':int(match.group('size'))}
    return None
