"""Native model response contract. No user-text classification or canned FAQ."""
import json,os,re,unicodedata
from pathlib import Path
from tool_payload import pairs
STATES={'understood','partial','unclear'}
MONEY=re.compile(r'(?<!\w)\d[\d.,]*\s*(?:k(?!\w)|đ(?:ồng)?(?!\w)|₫|vnd(?!\w))',re.I)
class InvalidDialogue(ValueError):pass

def enabled():
    value=os.getenv('MERLY_DIALOGUE_CONTRACT_ENABLED','1')
    if value not in ('0','1'):raise ValueError('invalid_dialogue_contract_flag')
    return value=='1'

def instructions():
    return '\n\n'+Path(__file__).with_name('DIALOGUE-CONTRACT.md').read_text() if enabled() else ''

def parse(raw):
    if not enabled():return {'understanding':'legacy','reply':raw,'question':'','options':[]}
    try:d=json.loads(raw,object_pairs_hook=pairs)
    except (ValueError,TypeError):raise InvalidDialogue('invalid_dialogue_json') from None
    if not isinstance(d,dict) or set(d)!={'understanding','reply','question','options'}:raise InvalidDialogue('invalid_dialogue_shape')
    if not isinstance(d['understanding'],str) or d['understanding'] not in STATES:raise InvalidDialogue('invalid_understanding')
    for key,limit in (('reply',6000),('question',500)):
        if not isinstance(d[key],str) or len(d[key])>limit or '\x00' in d[key]:raise InvalidDialogue('invalid_dialogue_text')
    options=d['options']
    if not isinstance(options,list) or len(options) not in (0,2,3) or any(not isinstance(x,str) or not x.strip() or len(x)>120 or any(ord(c)<32 for c in x) for x in options):raise InvalidDialogue('invalid_options')
    if len(set(options))!=len(options):raise InvalidDialogue('duplicate_options')
    if (d['understanding']!='understood' or options) and not d['question'].strip():raise InvalidDialogue('clarification_question_required')
    if not (d['reply'].strip() or d['question'].strip()):raise InvalidDialogue('empty_dialogue')
    return d

def text(d):return '\n'.join(s for s in (d['reply'].strip(),d['question'].strip()) if s)

def safe_clarification(d):
    """Conservative output evidence guard, never applied to customer input."""
    from turn_contract import PROTOCOL
    raw=text(d)+'\n'+'\n'.join(d['options'])
    folded=''.join(c for c in unicodedata.normalize('NFD',d['reply'].casefold().replace('đ','d')) if unicodedata.category(c)!='Mn')
    return not (PROTOCOL.search(raw) or re.search(r'https?://\S*/products/',raw,re.I) or MONEY.search(d['reply']) or re.search(r'\b(?:con hang|het hang|co san|san hang|in stock|sold out)\b',folded))
