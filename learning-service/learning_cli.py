"""Local owner review. No model invocation, production edit or live chat request."""
import argparse,json,os
from learning_store import Store,ReviewError
from learning_contract import InvalidEvent
from recipes import RECIPES

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state-dir',default=os.getenv('MERLY_LEARNING_STATE_DIR','/data'))
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('list','report','purge','analyze'):sub.add_parser(name)
    mark=sub.add_parser('mark');mark.add_argument('diagnostic_id')
    show=sub.add_parser('show');show.add_argument('case_id')
    propose=sub.add_parser('propose');propose.add_argument('case_id');propose.add_argument('--recipe',choices=sorted(RECIPES))
    review=sub.add_parser('review');review.add_argument('lesson_id');review.add_argument('--decision',required=True,choices=('approve','reject','revoke'));review.add_argument('--owner-confirmed',action='store_true')
    export=sub.add_parser('export');export.add_argument('lesson_id')
    args=p.parse_args(argv)
    try:
        store=Store(args.state_dir)
        if args.command=='list':result=store.list_cases()
        elif args.command=='report':result=store.report()
        elif args.command=='analyze':result=store.analyze()
        elif args.command=='purge':result={'deleted':store.purge()}
        elif args.command=='mark':result=store.mark(args.diagnostic_id)
        elif args.command=='show':result=store.case(args.case_id)
        elif args.command=='propose':result=store.propose(args.case_id,args.recipe)
        elif args.command=='review':result=store.review(args.lesson_id,args.decision,args.owner_confirmed)
        else:result={'path':store.export_file(args.lesson_id),'deployment_authorized':False}
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (ReviewError,InvalidEvent):
        print(json.dumps({'error':'review_request_rejected','details':'Check ID/state/owner confirmation; no change was applied.'}));return 2
    except FileExistsError:
        print(json.dumps({'error':'export_already_exists','overwritten':False}));return 2
if __name__=='__main__':raise SystemExit(main())
