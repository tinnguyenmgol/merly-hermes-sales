"""Signed startup inventory for dedicated sales runtime. Not OS sandboxing."""
import hashlib,hmac,json,os,time
from pathlib import Path
NAMES={'mcp__merly__'+name for name in ('search_products','quote_variant','size_guide','get_policy','get_promotions')}
class AuditError(ValueError):pass

def digest(record,key):
    raw=json.dumps(record,sort_keys=True,separators=(',',':')).encode()
    return hmac.new(key.encode(),raw,hashlib.sha256).hexdigest()

def verify_attestation(base,key):
    try:
        path=Path(os.environ['HERMES_SALES_ATTESTATION']);item=json.loads(path.read_text());record=item['record']
        if not hmac.compare_digest(digest(record,key),item['signature']):raise AuditError('signature_invalid')
        if record['api_base']!=base or set(record['tools'])!=NAMES:raise AuditError('wrong_sales_runtime')
        if record['memory_enabled'] is not False or record['user_profile_enabled'] is not False:raise AuditError('shared_memory_enabled')
        age=time.time()-record['created_at']
        if not 0<=age<=86400:raise AuditError('startup_inventory_expired')
        return record
    except (OSError,KeyError,TypeError,ValueError):raise AuditError('sales_runtime_attestation_required') from None
