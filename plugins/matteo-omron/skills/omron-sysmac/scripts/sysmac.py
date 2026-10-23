"""Esporta progetti Omron Sysmac Studio (cache Solution / repo VC) in testo compatto per LLM.

  python -I sysmac.py list [filtro]
  python -I sysmac.py export <guid|filtro> [--out DIR] [--latest]
  python -I sysmac.py diff <exportA> <exportB>

Sola lettura su C:\\OMRON\\Data. Formato interno non documentato: vedi references/formato-sysmac.md.
"""
from pathlib import Path
import sys, os, re, json, hashlib, shutil, difflib, html
import xml.etree.ElementTree as ET
from datetime import datetime

DATA = Path(os.environ.get('OMRON_DATA', r'C:\OMRON\Data'))
OUT_ROOT = Path(os.environ.get('OMRON_EXPORT_ROOT', r'C:\Users\Matteo\Documents\AI_Projects\OMRON'))
SKIP_CFG = {'PouBodySourceHolder', 'SourceHolder', 'BookmarkGroup', 'DebugProgramSetting', 'Watch', 'GridWatch',
            'Simulation', 'ProjectShortcut', 'Solution', 'UserProgramId', 'Inline', 'ConditionMonitor'}
POU_TYPES = {'Program': 'PROGRAM', 'FunctionBlock': 'FUNCTION_BLOCK', 'Function': 'FUNCTION'}


def read_text(p):
    raw = p.read_bytes()
    for enc in ('utf-8-sig', 'utf-16'):
        try:
            return raw, raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw, raw.decode('utf-8', errors='replace')


def unescape(s):
    return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)), s or '')


# ---------------------------------------------------------------- progetti
def projects():
    dirs = [(d, 'SOL') for d in DATA.glob('Solution/*') if d.is_dir()]
    dirs += [(d / 'Project', 'VC:' + d.name) for d in DATA.glob('VC/*') if (d / 'Project').is_dir()]
    out = []
    for d, src in dirs:
        m2 = next(d.glob('*.manifest2'), None)
        oem = next(d.glob('*.oem'), None)
        if not m2 or not oem:
            continue
        txt = m2.read_text(encoding='utf-8-sig', errors='replace')
        name = re.search(r'solutionName="([^"]*)"', txt)
        cpu = re.search(r'name="SetUnit ([^"]*)"', txt)
        out.append(dict(dir=d, src=src, guid=oem.stem, name=html.unescape(name[1]) if name else '?',
                        cpu=cpu[1] if cpu else '', mtime=oem.stat().st_mtime,
                        open=any(d.glob('*.applicationlock'))))
    return sorted(out, key=lambda p: -p['mtime'])


def select(arg, latest=False):
    ps = projects()
    if Path(arg).is_dir():  # percorso diretto (Solution/<GUID> o VC/<nome>/Project)
        hit = [p for p in ps if p['dir'].resolve() == Path(arg).resolve()]
        if hit:
            return hit[0]
    hit = [p for p in ps if p['guid'].startswith(arg.lower())] or \
          [p for p in ps if arg.lower() in (p['name'] + ' ' + p['src']).lower()]
    if len(hit) == 1 or (hit and latest):
        return hit[0]
    print_list(hit or ps[:20])
    sys.exit(f'\n{len(hit)} progetti corrispondono a "{arg}": usa il GUID o --latest')


def print_list(ps):
    for p in ps:
        t = datetime.fromtimestamp(p['mtime']).strftime('%Y-%m-%d %H:%M')
        print(f"{p['guid'][:8]}  {t}  {'APERTO ' if p['open'] else ''}{p['src']:<8.40}  {p['name']}  [{p['cpu']}]")


# ---------------------------------------------------------------- struttura (.oem)
def tree(d):
    root = ET.parse(next(d.glob('*.oem'))).getroot()
    ents = {}

    def walk(e, path, parent):
        for c in e.findall('./ChildEntities/Entity'):
            p = path + [c.get('name', '')]
            ents[c.get('id')] = dict(id=c.get('id'), type=c.get('type'), sub=c.get('subtype', ''),
                                     name=c.get('name', ''), path=p, parent=parent, kids=[])
            if parent in ents:
                ents[parent]['kids'].append(c.get('id'))
            walk(c, p, c.get('id'))
    for e in root.findall('Entity'):
        walk(e, [], e.get('id'))
    return ents


# ---------------------------------------------------------------- variabili (SLWD)
def parse_slwd(text):
    vs = []
    for line in text.splitlines():
        if not line.startswith('++'):
            continue
        kv = dict(x.split('=', 1) for x in line[2:].split('\t') if '=' in x)
        vs.append(kv)
    return vs


def var_line(v):
    s = f"{v.get('N')} : {v.get('D')}"
    if v.get('IV'):
        s += f" := {v['IV']}"
    flags = [f for k, f in (('R', 'RETAIN'), ('Const', 'CONST'), ('RO', 'RO')) if v.get(k) == '1']
    if v.get('AT'):
        flags.append('AT ' + v['AT'])
    if v.get('E'):
        flags.append('EDGE ' + v['E'])
    if v.get('NTP') in ('PublicationInput', 'PublicationOutput'):
        flags.append(v['NTP'].replace('Publication', 'NET-'))
    s += ';'
    if flags:
        s += ' {' + ', '.join(flags) + '}'
    com = html.unescape(v.get('Com', ''))
    ecs = re.findall(r'EK="([^"]*)" C="([^"]*)"', html.unescape(v.get('EC', '')))
    if ecs:
        com += ' [' + '; '.join(f'{k}={html.unescape(c)}' for k, c in ecs) + ']'
    return s + (f' // {com.strip()}' if com.strip() else '')


def render_vars(vs, compact_external=True):
    groups = {}
    for v in vs:
        groups.setdefault(v.get('G', 'VAR'), []).append(v)
    out = []
    for g, items in groups.items():
        if g == 'VAR_EXTERNAL' and compact_external:
            out.append('VAR_EXTERNAL (globali usate): ' + ', '.join(v['N'] for v in items))
            continue
        out.append(g)
        out += ['  ' + var_line(v) for v in items]
        out.append('END_VAR')
    return out


# ---------------------------------------------------------------- tipi dati
def render_types(text):
    root = ET.fromstring(text.encode('utf-8'))
    out = []

    def t_of(e):
        return e.get('BaseType') or e.get('ArrayType') or '?'

    def com(e):
        return f" // {e.get('Comment')}" if e.get('Comment') else ''

    def emit(e, ind):
        kids = [k for k in e.findall('DataType') if k.get('IsControllerDefinedType') != 'true']
        bt = e.get('BaseType')
        if bt in ('STRUCT', 'UNION'):
            out.append(f"{ind}TYPE {e.get('Name')} : {bt}{com(e)}")
            for k in kids:
                if k.get('BaseType') in ('STRUCT', 'UNION', 'ENUM') and k.findall('DataType'):
                    emit(k, ind + '  ')
                else:
                    iv = f" := {k.get('InitialValue')}" if k.get('InitialValue') else ''
                    out.append(f"{ind}  {k.get('Name')} : {t_of(k)}{iv};{com(k)}")
            out.append(f'{ind}END_{bt}')
        elif bt == 'ENUM':
            vals = ', '.join(f"{k.get('Name')}:={k.get('EnumValue')}" for k in kids)
            out.append(f"{ind}TYPE {e.get('Name')} : ({vals});{com(e)}")
        elif not bt and kids:  # cartella / namespace
            out.append(f"{ind}// --- {e.get('Name')}")
            for k in kids:
                emit(k, ind)
        elif bt:
            out.append(f"{ind}TYPE {e.get('Name')} : {bt};{com(e)}")
    for top in root.findall('DataType'):
        for k in top.findall('DataType'):
            if k.get('IsControllerDefinedType') != 'true':
                emit(k, '')
    return out


# ---------------------------------------------------------------- ladder -> espressioni
CMP = {'=', '<>', '<', '>', '<=', '>=', 'EQ', 'NE', 'LT', 'GT', 'LE', 'GE'}


class Raw(Exception):
    pass


def AND(*xs):
    terms = []
    for x in xs:
        if x == 'FALSE':
            return 'FALSE'
        if x != 'TRUE':
            terms += list(x[1]) if isinstance(x, tuple) and x[0] == '&' else [x]
    return 'TRUE' if not terms else terms[0] if len(terms) == 1 else ('&', tuple(terms))


def OR(*xs):
    xs = list(dict.fromkeys(x for x in xs if x is not None))
    if not xs:
        return None
    if 'TRUE' in xs:
        return 'TRUE'
    if len(xs) == 1:
        return xs[0]
    seqs = [list(x[1]) if isinstance(x, tuple) and x[0] == '&' else [x] for x in xs]
    n = 0
    while all(len(q) > n for q in seqs) and all(q[n] == seqs[0][n] for q in seqs):
        n += 1
    if n:  # fattorizza il prefisso comune: a AND b OR a AND c -> a AND (b OR c)
        return AND(*seqs[0][:n], OR(*[AND(*q[n:]) for q in seqs]))
    alts = []
    for x in xs:
        alts += list(x[1]) if isinstance(x, tuple) and x[0] == '|' else [x]
    return ('|', tuple(dict.fromkeys(alts)))


def show(e):
    if not isinstance(e, tuple):
        return e
    if e[0] == '|':
        return ' OR '.join(show(x) for x in e[1])
    return ' AND '.join(f'({show(x)})' if isinstance(x, tuple) and x[0] == '|' else show(x) for x in e[1])


def contact(c):
    v = c.get('Var', '?')
    if c.get('Up'):
        v = '↑' + v
    if c.get('Dwn'):
        v = '↓' + v
    return 'NOT ' + v if c.get('Not') else v


def args(c, conn):
    """parametri F/FB: (ingressi, uscite) come testo; conn = espressioni collegate per riga."""
    ins, outs = [], []
    for i, a in enumerate(c.get('In', [])):
        if a.get('__type') == 'PF':
            continue
        val = a.get('Var') or conn.get(i)
        if val:
            pre = ('NOT ' if a.get('Not') else '') + ('↑' if a.get('Up') else '')
            ins.append(f"{a.get('Arg')}:={pre}{val}" if a.get('Arg') else pre + val)
    for a in c.get('Out', []):
        if a.get('__type') == 'PF' or not a.get('Var') or a.get('IO'):
            continue
        outs.append(f"{a.get('Arg')}=>{a['Var']}" if a.get('Arg') else f"=> {a['Var']}")
    return ins, outs


def rung_logic(r):
    cls = r.get('CLs', [])
    if not cls:
        return []
    known = {'LD', 'ST', 'HL', 'F', 'FB', 'IST', 'JMP'}
    if any(c.get('__type') not in known for c in cls):
        raise Raw('elemento sconosciuto')
    grid, maxx = {}, 0
    for c in cls:  # ogni elemento occupa una cella (X,Y); F/FB sono alti una riga logica
        x, y = c.get('X', 0), c.get('Y', 0)
        if (x, y) in grid:
            raise Raw('celle sovrapposte')
        grid[(x, y)] = c
        maxx = max(maxx, x)
    vl = {}
    for v in r.get('VLs', []):  # VL @x,y collega i nodi sinistri della colonna x tra riga y e y+1
        vl.setdefault(v.get('X', 0), set()).add(v.get('Y', 0))
    nodes = {}   # (x, y) -> potenza sul nodo sinistro della colonna x
    acts = []

    def merge(x):
        col = {y: e for (xx, y), e in nodes.items() if xx == x}
        links = vl.get(x, set())
        ys = sorted(set(col) | links | {y + 1 for y in links})
        groups, cur = [], []
        for y in ys:
            cur.append(y)
            if y not in links:
                groups.append(cur)
                cur = []
        for g in groups + ([cur] if cur else []):
            e = OR(*[col.get(y) for y in g])
            for y in g:
                nodes[(x, y)] = e

    for x in range(maxx + 1):
        if x:
            merge(x)
        for (cx, y), c in sorted(grid.items()):
            if cx != x:
                continue
            t = c['__type']
            pw = 'TRUE' if x == 0 else nodes.get((x, y))
            if pw is None:
                raise Raw(f'nodo senza alimentazione @{x},{y}')
            nxt = pw
            if t == 'LD':
                nxt = AND(pw, contact(c))
            elif t == 'ST':
                op = 'S' if c.get('S') else 'R' if c.get('RS') else '=NOT' if c.get('Not') else '='
                acts.append(((y, x), '↑' if c.get('Up') else '↓' if c.get('Dwn') else '', pw, f"{op} {c.get('Var', '?')}"))
            elif t == 'JMP':
                acts.append(((y, x), '', pw, f"JMP {c.get('Label')}"))
            elif t == 'IST':
                acts.append(((y, x), '', pw, 'ST: ' + unescape(c.get('TXT', '')).replace('\r\n', '\n').replace('\n', '\n      ')))
            elif t in ('F', 'FB'):
                ins, outs = args(c, {})
                name = c.get('Name', '?')
                pf_in = next((a for a in c['In'] if a.get('__type') == 'PF'), {})
                pf_out = next((a for a in c['Out'] if a.get('__type') == 'PF'), {})
                if t == 'F' and c.get('PL'):  # funzione-contatto (confronti ecc.)
                    vals = [s.split(':=', 1)[-1] for s in ins]
                    nxt = AND(pw, '(' + f' {name} '.join(vals) + ')' if name in CMP and len(vals) >= 2
                              else f"{name}({', '.join(ins)})")
                elif t == 'FB':
                    inst = c.get('Var', '?')
                    pin = (pf_in.get('Arg') or 'EN') + ':=' + ('↑' if pf_in.get('Up') else '')
                    acts.append(((y, x), '', 'TRUE', f"{inst}({pin}{show(pw)}{''.join(', ' + s for s in ins + outs)}) : {name}"))
                    nxt = f"{inst}.{pf_out.get('Arg') or 'ENO'}"
                else:
                    acts.append(((y, x), '', pw, f"{name}({', '.join(ins + outs)})"))
            nodes[(x + 1, y)] = nxt
    return [(f'{e}({show(pw)})' if e else show(pw), a) for _, e, pw, a in sorted(acts, key=lambda t: t[0])]


def rung_raw(r):
    out = []
    for c in r.get('CLs', []):
        t = c.get('__type')
        pos = f"@{c.get('X', 0)},{c.get('Y', 0)}"
        if t == 'LD':
            out.append(f'LD {contact(c)} {pos}')
        elif t == 'ST':
            out.append(f"ST {'S ' if c.get('S') else 'R ' if c.get('RS') else ''}{c.get('Var')} {pos}")
        elif t in ('F', 'FB'):
            ins, outs = args(c, {})
            out.append(f"{t} {c.get('Var', '')}:{c.get('Name')}({', '.join(ins + outs)}) {pos}")
        elif t == 'IST':
            out.append(f"ST-INLINE {pos}: {unescape(c.get('TXT', ''))}")
        elif t != 'HL':
            out.append(f'{t} {json.dumps({k: v for k, v in c.items() if k != "__type"}, ensure_ascii=False)} {pos}')
    if r.get('VLs'):
        out.append('VL ' + ' '.join(f"@{v.get('X', 0)},{v.get('Y', 0)}" for v in r['VLs']))
    return out


def render_ladder(text):
    out, stats = [], dict(rungs=0, raw=0)
    for line in text.splitlines():
        if not line.startswith('{'):
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if 'CLs' not in r:
            continue
        stats['rungs'] += 1
        cmt = unescape(r.get('CMT', '')).replace('\r\n', ' / ').replace('\n', ' / ').strip()
        out.append(f"R{stats['rungs']}" + (f' // {cmt}' if cmt else ''))
        try:
            acts = rung_logic(r)
            groups = []  # raggruppa solo azioni consecutive con la stessa condizione (ordine alto->basso)
            for cond, a in acts:
                if groups and groups[-1][0] == cond:
                    groups[-1][1].append(a)
                else:
                    groups.append((cond, [a]))
            for cond, al in groups:
                if cond == 'TRUE':
                    out += ['  ' + a for a in al]
                else:
                    out.append(f'  {cond}')
                    out += ['    -> ' + a for a in al]
        except Raw as e:
            stats['raw'] += 1
            out.append(f'  ?LADDER-RAW ({e})')
            out += ['    ' + s for s in rung_raw(r)]
    return out, stats


# ---------------------------------------------------------------- corpo POU
def render_body(text):
    if 'EncryptedFile' in text[:400]:
        return ['[POU PROTETTO - corpo cifrato]'], dict(kind='protetto')
    if text.lstrip().startswith('{'):
        out, st = render_ladder(text)
        return out, dict(kind='Ladder', **st)
    if '<StructuredTextModel' in text[:200]:
        root = ET.fromstring(text.encode('utf-8'))
        body = next((e.text for e in root.iter() if e.tag.endswith('Text')), None)
        if body is None:
            body = root.text or ''
        if 'EncryptedFile' in body[:400]:
            return ['[POU PROTETTO - corpo cifrato]'], dict(kind='protetto')
        lines = body.replace('\r\n', '\n').split('\n')
        return lines, dict(kind='ST', lines=len(lines))
    return ['[formato corpo non riconosciuto]'], dict(kind='?')


# ---------------------------------------------------------------- config generica
def compact_xml(text):
    try:
        root = ET.fromstring(text.encode('utf-8'))
    except ET.ParseError:
        return text.splitlines()
    out = []

    def walk(e, d):
        tag = e.tag.split('}')[-1]
        attrs = ' '.join(f'{k.split("}")[-1]}={v}' for k, v in e.attrib.items() if v not in ('', None) and 'Id' not in k)
        txt = (e.text or '').strip()
        line = '  ' * d + tag + (' ' + attrs if attrs else '') + (f' = {txt[:300]}' if txt else '')
        if attrs or txt or len(e):
            out.append(line)
        for c in e:
            walk(c, d + 1)
    walk(root, 0)
    return out


# ---------------------------------------------------------------- export
def slug(s):
    return re.sub(r'[^\w.-]+', '_', s).strip('_')[:80] or 'x'


def default_out(p):
    m = re.match(r'\s*0*(\d+)\s*-\s*([^-]+?)\s*(?:-|$)', p['name'])
    base = f"{m[1]}_{slug(m[2].split()[0].lower())}" if m else slug(p['name'])
    ver = p['name'].rsplit(' - ', 1)[-1] if ' - ' in p['name'] else ''
    ver = slug(ver) if re.search(r'\d', ver) and len(ver) < 15 else ('vc' if p['src'].startswith('VC') else 'sysmac')
    return OUT_ROOT / base / f'export_{ver}'


def export(p, out):
    d = p['dir']
    if out.exists():
        if not (out / 'manifest.json').exists():
            sys.exit(f'{out} esiste e non e un export di sysmac.py: scegli --out')
        shutil.rmtree(out)
    out.mkdir(parents=True)
    ents = tree(d)
    manifest, written, index = [], set(), []
    xml_of = {i: d / f'{i}.xml' for i in ents if (d / f'{i}.xml').exists()}

    def save(rel, lines, eids):
        rel = rel.replace('\\', '/')
        while rel in written:
            rel = rel.replace('.', '_.', 1)
        written.add(rel)
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        for i in eids:
            raw = xml_of[i].read_bytes()
            manifest.append(dict(guid=i, type=ents[i]['type'], path=' / '.join(ents[i]['path']), file=rel,
                                 sha256=hashlib.sha256(raw).hexdigest()))
        return rel

    done, raw_total = set(), 0
    # POU: un file se una sola sezione, altrimenti cartella con _variabili.st + una sezione per file
    pous = [e for e in ents.values() if e['type'] in POU_TYPES]
    pou_rows = []
    for e in sorted(pous, key=lambda e: e['path']):
        kids = [ents[k] for k in e['kids']]
        varf = [k for k in kids if k['type'] == 'Variables' and k['id'] in xml_of]
        bodies = [k for k in kids if k['type'] == 'PouBody']
        try:
            rel = '/'.join(slug(x) for x in e['path'][e['path'].index('POUs') + 1:])
        except ValueError:
            rel = '/'.join(slug(x) for x in e['path'][-3:])
        head = f"// {POU_TYPES[e['type']]} {e['name']}  ({e['sub']})  -- {' / '.join(e['path'])}"
        vlines, veids = [], []
        for v in varf:
            vlines += render_vars(parse_slwd(read_text(xml_of[v['id']])[1]))
            veids.append(v['id'])
        secs = []
        for b in bodies:
            if b['id'] not in xml_of:
                secs.append((b, ['[corpo non presente in XML - es. safety]'], 'n/d'))
                continue
            body, st = render_body(read_text(xml_of[b['id']])[1])
            raw_total += st.get('raw', 0)
            desc = st['kind'] + (f", {st['rungs']} reti" if 'rungs' in st else '') + \
                (f", {st['raw']} RAW" if st.get('raw') else '') + (f", {st['lines']} righe" if 'lines' in st else '')
            secs.append((b, body, desc))
        done.update(veids + [b['id'] for b, _, _ in secs if b['id'] in xml_of])
        kind = f"{POU_TYPES[e['type']]} | {e['sub']}"
        if not veids and not any(b['id'] in xml_of for b, _, _ in secs):
            pou_rows.append(f"| {e['name']} | {kind} | - | non in XML (safety/libreria) |")
        elif len(secs) <= 1:
            lines = [head] + vlines
            for b, body, desc in secs:
                lines += ['', f"// ==== {b['name']} ({desc})"] + body
            f = save(f'pou/{rel}.st', lines, veids + [b['id'] for b, _, _ in secs if b['id'] in xml_of])
            pou_rows.append(f"| {e['name']} | {kind} | [{f}]({f}) | {secs[0][2] if secs else '-'} |")
        else:
            f = save(f'pou/{rel}/_variabili.st', [head] + vlines, veids)
            pou_rows.append(f"| {e['name']} | {kind} | [{f}]({f}) | {len(secs)} sezioni (sotto) |")
            for n, (b, body, desc) in enumerate(secs, 1):
                ids = [b['id']] if b['id'] in xml_of else []
                fs = save(f"pou/{rel}/{n:02d}_{slug(b['name'])}.st",
                          [f"// {e['name']} / sezione {n}: {b['name']} ({desc})  -- variabili in _variabili.st"] + body, ids)
                pou_rows.append(f"| ↳ {b['name']} | sezione {n} | [{fs}]({fs}) | {desc} |")
    # variabili globali, tipi, task
    globs = [e for e in ents.values() if e['type'] == 'Variables' and e['id'] in xml_of and e['id'] not in done]
    for g in globs:
        save(f"vars/{slug(g['name'])}.st", render_vars(parse_slwd(read_text(xml_of[g['id']])[1]), False), [g['id']])
        done.add(g['id'])
    for t in [e for e in ents.values() if e['type'] == 'DataType' and e['id'] in xml_of]:
        save('types.st', render_types(read_text(xml_of[t['id']])[1]), [t['id']])
        done.add(t['id'])
    tasks = []
    for t in [e for e in ents.values() if e['type'] == 'NexTask' and e['id'] in xml_of]:
        x = read_text(xml_of[t['id']])[1]
        per = re.search(r'TaskExecutionCondition="(\d+)"', x)
        pri = re.search(r'ExecutionPriority="(\d+)"', x)
        progs = re.findall(r'ProgramName="([^"]*)"', x)
        tasks.append(f"| {t['name']} | {int(per[1]) / 1000 if per else '?'} ms | {pri[1] if pri else '?'} | {', '.join(progs)} |")
        done.add(t['id'])
    # config residua
    cfg_rows, skipped = [], {}
    for i, f in xml_of.items():
        e = ents[i]
        if i in done:
            continue
        if e['type'] in SKIP_CFG:
            skipped[e['type']] = skipped.get(e['type'], 0) + 1
            continue
        lines = compact_xml(read_text(f)[1])
        if len(lines) <= 1:
            skipped['vuoti'] = skipped.get('vuoti', 0) + 1
            continue
        rel = save(f"config/{slug(e['type'])}_{slug(e['name'])}.txt", lines, [i])
        cfg_rows.append(f"| {e['type']} | {e['name']} | [{rel}]({rel}) | {len(lines)} |")
    orphans = [f.name for f in d.glob('*.xml') if f.stem not in ents]

    t = datetime.fromtimestamp(p['mtime']).strftime('%Y-%m-%d %H:%M')
    index = [f"# {p['name']}", '',
             f"- Sorgente: `{d}` ({p['src']}, GUID {p['guid']}), oem modificato {t}{', APERTO in Sysmac' if p['open'] else ''}",
             f"- CPU: {p['cpu'] or '?'}", f"- Export: {datetime.now():%Y-%m-%d %H:%M} con sysmac.py (sola lettura). "
             'Le modifiche vanno fatte in Sysmac Studio.', '',
             '## Legenda ladder', '`R<n> // commento` = rete. Riga = condizione di potenza; `-> = X` bobina, `-> =NOT X` bobina negata, '
             '`-> S X`/`-> R X` set/reset, `↑x`/`↓x` fronte salita/discesa, `Inst(In:=cond, ...) : TIPO` chiamata FB, '
             '`ST:` ST inline. `?LADDER-RAW` = topologia non risolta: elementi con coordinate @x,y.', '']
    if tasks:
        index += ['## Task', '| Task | Periodo | Priorita | Programmi |', '|---|---|---|---|'] + tasks + ['']
    index += ['## POU', '| Nome | Tipo | Linguaggio | File | Contenuto |', '|---|---|---|---|---|'] + pou_rows + ['']
    index += ['## Dati', '- Variabili globali: ' + ', '.join(f'[vars/{slug(g["name"])}.st](vars/{slug(g["name"])}.st)' for g in globs),
              '- Tipi utente: [types.st](types.st)', '']
    cfg_types = {}
    for r in cfg_rows:
        t = r.split(' | ')[0][2:]
        cfg_types[t] = cfg_types.get(t, 0) + 1
    (out / 'config').mkdir(exist_ok=True)
    cfg_index = ['| Tipo | Nome | File | Righe |', '|---|---|---|---|'] + [r.replace('](config/', '](') for r in sorted(cfg_rows)]
    (out / 'config' / 'INDEX.md').write_text('\n'.join(cfg_index) + '\n', encoding='utf-8')
    index += ['## Configurazione', f'{len(cfg_rows)} file, elenco in [config/INDEX.md](config/INDEX.md). Tipi: ' +
              ', '.join(f'{k}×{v}' for k, v in sorted(cfg_types.items())), '']
    index += [f"Esclusi (non codice): {', '.join(f'{k}×{v}' for k, v in sorted(skipped.items()))}"]
    if orphans:
        index += [f'XML senza voce in .oem (ignorati): {len(orphans)}']
    (out / 'INDEX.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    (out / 'manifest.json').write_text(json.dumps(dict(generator='sysmac.py', project=p['name'], guid=p['guid'],
                                                       source=str(d), files=manifest), indent=1, ensure_ascii=False),
                                       encoding='utf-8')
    size = sum(f.stat().st_size for f in out.rglob('*') if f.is_file())
    print(f"{out}\n{len(pous)} POU, {len(cfg_rows)} config, {size // 1024} KB, reti RAW: {raw_total}")


# ---------------------------------------------------------------- diff
def diff(a, b):
    ma = {x['guid']: x for x in json.loads((a / 'manifest.json').read_text(encoding='utf-8'))['files']}
    mb = {x['guid']: x for x in json.loads((b / 'manifest.json').read_text(encoding='utf-8'))['files']}
    changed = sorted({mb[g]['file'] for g in mb if g in ma and ma[g]['sha256'] != mb[g]['sha256']})
    added = sorted({mb[g]['path'] for g in mb.keys() - ma.keys()})
    removed = sorted({ma[g]['path'] for g in ma.keys() - mb.keys()})
    for s in added:
        print('+ ' + s)
    for s in removed:
        print('- ' + s)
    for f in changed:
        fa, fb = a / f, b / f
        la = fa.read_text(encoding='utf-8').splitlines() if fa.exists() else []
        lb = fb.read_text(encoding='utf-8').splitlines() if fb.exists() else []
        d = list(difflib.unified_diff(la, lb, f'A/{f}', f'B/{f}', n=3, lineterm=''))
        if d:
            print('\n'.join(d))
    print(f'\n{len(changed)} file modificati, {len(added)} aggiunti, {len(removed)} rimossi')


def main(argv):
    if not argv or argv[0] not in ('list', 'export', 'diff'):
        sys.exit(__doc__)
    sys.stdout.reconfigure(encoding='utf-8')
    if argv[0] == 'list':
        f = argv[1].lower() if len(argv) > 1 else ''
        print_list([p for p in projects() if f in (p['name'] + p['src'] + p['guid']).lower()])
    elif argv[0] == 'export':
        out = Path(argv[argv.index('--out') + 1]) if '--out' in argv else None
        p = select(argv[1], '--latest' in argv)
        export(p, out or default_out(p))
    else:
        diff(Path(argv[1]), Path(argv[2]))


if __name__ == '__main__':
    main(sys.argv[1:])
