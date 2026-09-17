"""GitHub release endpoint used by the in-app update checker."""
import re
REPOSITORY = 'eternitylzt/AsterPDF'

def newer(tag,installed):
    def version(s):
        match=re.search(r'(?:^|v)(\d+)\.(\d+)\.(\d+)$',s)
        return tuple(map(int,match.groups())) if match else None
    latest,current=version(tag),version(installed)
    return latest is not None and current is not None and latest>current
