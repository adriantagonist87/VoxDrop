"""Presentation of structured download events; no model or network imports."""
from datetime import datetime
import json

EVENT='voxdrop-download:'


def parse_event(line):
    if not line.startswith(EVENT):return None
    try:
        value=json.loads(line[len(EVENT):])
        return value if isinstance(value,dict) else None
    except (TypeError,ValueError):return None


def byte_text(value):
    if value is None:return 'unbekannt'
    value=max(0,float(value))
    for unit in ('B','KiB','MiB','GiB','TiB'):
        if value<1024 or unit=='TiB':
            return f'{int(value)} {unit}' if unit=='B' else f'{value:.2f} {unit}'
        value/=1024


def merge_servers(previous,incoming):
    servers={item['id']:item for item in previous}
    for item in incoming:
        if item.get('checkedAt',0)>=servers.get(item['id'],{}).get('checkedAt',0):
            servers[item['id']]=item
    return list(servers.values())


def present(status):
    phase=status.get('phase','idle')
    total=status.get('bytesTotal')
    done=status.get('bytesCompleted',0)
    fraction=min(1,max(0,done/total)) if total else None
    files=[]
    labels=dict(waiting='Wartet',present='Vorhanden, noch nicht geprüft',
                downloading='Wird geladen',downloaded='Geladen, noch nicht verifiziert',verified='Geprüft')
    for item in status.get('files',[]):
        size=item.get('size');position=item.get('done',0)
        label=labels.get(item.get('status'),'Wartet')
        if item.get('cached') and item.get('status')=='downloaded':label='Aus dem Cache, noch nicht verifiziert'
        files.append(dict(name=item['name'],model=item['model'],
            amount=byte_text(position)+' / '+byte_text(size),
            fraction=min(1,max(0,position/size)) if size else None,
            status=label,cached=bool(item.get('cached'))))
    servers=[]
    for server in status.get('servers',[]):
        checked=server.get('checkedAt')
        state=server.get('state')
        label=dict(api='Modellzugriff',files='Dateiserver',transfer='Datenübertragung').get(server.get('role'),'Server')
        servers.append(dict(text=f"{server.get('model','')} · {label} · {server.get('host','')}: {server.get('detail','')}",
            checking=state=='checking',error=state=='unconfirmed',
            checked=datetime.fromtimestamp(checked).strftime('%H:%M:%S') if checked else '',
            latency=(str(server['latencyMs'])+' ms') if server.get('latencyMs') is not None else ''))
    active=[item for item in files if item['status']=='Wird geladen']
    wait=status.get('waitingSeconds')
    waiting=f'Keine neuen Daten seit {int(wait)} s.' if phase=='downloading' and wait is not None and wait>=3 else ''
    return dict(phase=phase,message=status.get('message','Noch kein Download gestartet.'),
        fraction=fraction,summary='Dateidaten: '+byte_text(done)+' / '+byte_text(total)+
            (f' · {fraction:.0%}' if fraction is not None else ' · Gesamtgröße noch unbekannt'),
        rate=byte_text(status.get('bytesPerSecond',0))+'/s' if phase=='downloading' else 'Kein laufender Transfer',
        network=byte_text(status.get('networkTransferred',0))+' in diesem Versuch übertragen',
        current=(', '.join(item['name'] for item in active[:2])+ (f" (+{len(active)-2})" if len(active)>2 else '')),
        waiting=waiting,files=files,servers=servers,
        hasProgress=bool(files),error=phase=='error',finished=phase in ('complete','cancelled','error'))
