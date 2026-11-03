#!/usr/bin/env python3
# Converte un .cxt CX-Programmer (logica a bit, TIMHX, MOV, ++, confronti) in IEC 61131-10 XML per Sysmac Studio.
# Uso: python -I cxt_to_iec_xml.py sorgente.cxt uscita.xml
import re
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as esc

src, dst = sys.argv[1], sys.argv[2]
t = open(src, encoding='latin1').read().replace('\r', '')
SMC = 'https://www.ia.omron.com/Smc IEC61131_10_Ed1_0_SmcExt1_0_Spc1_0.xsd'


def PX(s):
    return f'<AddData><Data name="{SMC}" handleUnknown="discard">{s}</Data></AddData>'


# --- simboli
gv = re.search(r'BEGIN_LIST_\$#\[\d+\](.*?)END_LIST', t, re.S).group(1)
syms = {}
for l in gv.splitlines():
    r = l.strip().rstrip(';').split(',')
    if len(r) >= 3 and r[0]:
        syms[r[0]] = dict(name=r[0], addr=r[1], type=r[2], com=','.join(r[5:]).strip())
BITWORDS = ('Allarmi', 'Messaggi', 'FasiCicloSaldatura', 'FasiCicloPerno')
bitword = {s['addr']: s for s in syms.values() if s['name'] in BITWORDS}
tname = {s['addr']: s['name'] for s in syms.values() if re.fullmatch(r'T\d+', s['addr'])}

# --- preset timer dal blocco Memory (D in hex, unita' 10 ms)
dm = {}
mb = re.search(r'Memory:=\s*BEGIN\s*Data:=\s*\$\?St\$Bk\?_#\[\d+\]\n(.*?)\$\?St\$Bk', t, re.S).group(1)
txt = bytes(int(x, 16) for x in mb.split()).decode('latin1')
for it in re.search(r'\bD=([^\n]*)', txt).group(1).split(','):
    a, v = it.split(':')
    lo, hi = (a.split('-') + [a])[:2]
    for n in range(int(lo), int(hi) + 1):
        dm[n] = int(re.sub(r'[^0-9a-fA-F]', '', v) or '0', 16)


# --- I/O CP1E E40 -> built-in NX1P2 (0.xx/1.xx = Input 00-23, 100.xx/101.xx = Output 00-15)
def io_at(addr):
    m = re.fullmatch(r'(\d+)\.(\d+)', addr)
    if not m:
        return None
    w, b = int(m[1]), int(m[2])
    if w in (0, 1):
        return f'BuiltInIO://cpu/#0/Input_Bit_{w * 12 + b:02d}'
    if w in (100, 101):
        return f'BuiltInIO://cpu/#0/Output_Bit_{(w - 100) * 8 + b:02d}'
    raise ValueError(addr)


used, timers = set(), {}


def opnd(n):
    if n == 'P_First_Cycle':
        return 'P_First_RunMode'
    if n == 'ResetGen_Prec':
        used.add(n)
        return n
    s = syms[n]
    m = re.fullmatch(r'T(\d+)', s['addr'])
    if m:
        timers.setdefault(int(m[1]), n)
        return n + '.Q'
    if '.' in s['addr'] and s['addr'].split('.')[0] in bitword:
        w = bitword[s['addr'].split('.')[0]]
        used.add(w['name'])
        return f"{w['name']}.bit[{int(s['addr'].split('.')[1])}]"
    if s['addr'] in bitword:
        used.add(n)
        return n + '.W'
    used.add(n)
    return n


def val(v, typ):
    if v.startswith('&'):
        return 'WORD#16#' + format(int(v[1:]), 'X') if typ == 'WORD' else 'UINT#' + v[1:]
    if v.startswith('#'):
        return ('WORD#16#' if typ == 'WORD' else 'UINT#16#') + v[1:]
    return v


def word_type(n):
    return 'WORD' if syms[n]['addr'] in bitword else syms[n]['type']


class Rung:
    def __init__(self, com):
        self.com, self.ids, self.xml, self.right, self.left = com, 0, [], [], []

    def nid(self):
        self.ids += 1
        return self.ids

    def refs(self, ins):
        out = []
        for i in ins:
            if i == 'R':
                i = self.nid()
                self.left.append(i)
            out.append(i)
        return ''.join(f'<Connection refConnectionPointOutId="{i}"/>' for i in out)

    def lit(self, v):
        i = self.nid()
        self.xml.append(f'<FbdObject xsi:type="DataSource" identifier="{esc(v)}"><ConnectionPointOut connectionPointOutId="{i}"/></FbdObject>')
        return i

    def sink(self, v, i):
        self.xml.append(f'<FbdObject xsi:type="DataSink" identifier="{esc(v)}"><ConnectionPointIn><Connection refConnectionPointOutId="{i}"/></ConnectionPointIn></FbdObject>')

    def pin(self, name, refs, order):
        add = PX(f'<smcext:ConnectionPointInOrder order="{order}"/>')
        return f'<InputVariable parameterName="{name}"><ConnectionPointIn>{add}{refs}</ConnectionPointIn></InputVariable>'

    def pout(self, name, i, order):
        add = PX(f'<smcext:ConnectionPointOutOrder order="{order}"/>')
        return f'<OutputVariable parameterName="{name}"><ConnectionPointOut connectionPointOutId="{i}">{add}</ConnectionPointOut></OutputVariable>'

    def contact(self, name, neg, edge, ins):
        i_refs = self.refs(ins)
        i = self.nid()
        a = (' negated="true"' if neg else '') + (f' edge="{edge}"' if edge else '')
        self.xml.append(f'<LdObject xsi:type="Contact"{a} operand="{esc(opnd(name))}"><ConnectionPointIn>{i_refs}</ConnectionPointIn><ConnectionPointOut connectionPointOutId="{i}"/></LdObject>')
        return [i]

    def coil(self, name, latch, ins):
        i_refs = self.refs(ins)
        i = self.nid()
        a = f' latch="{latch}"' if latch else ''
        self.xml.append(f'<LdObject xsi:type="Coil"{a} operand="{esc(opnd(name))}"><ConnectionPointIn>{i_refs}</ConnectionPointIn><ConnectionPointOut connectionPointOutId="{i}"/></LdObject>')
        self.right.append(i)

    def cmp(self, op, a, b, ins):
        ia, ib = self.lit(opnd(a)), self.lit(val(b, word_type(a)))
        en = self.refs(ins)
        o = self.nid()
        ca = f'<Connection refConnectionPointOutId="{ia}"/>'
        cb = f'<Connection refConnectionPointOutId="{ib}"/>'
        self.xml.append(f'<FbdObject xsi:type="Block" typeName="{esc(op)}"><InputVariables>{self.pin("EN", en, 1)}{self.pin("In1", ca, 2)}{self.pin("In2", cb, 3)}</InputVariables><OutputVariables>{self.pout("", o, 1)}</OutputVariables></FbdObject>')
        return [o]

    def move(self, a, b, ins):
        ia = self.lit(val(a, word_type(b)))
        en_refs = self.refs(ins)
        en, o = self.nid(), self.nid()
        c = f'<Connection refConnectionPointOutId="{ia}"/>'
        self.xml.append(f'<FbdObject xsi:type="Block" typeName="MOVE"><InputVariables>{self.pin("EN", en_refs, 1)}{self.pin("In", c, 2)}</InputVariables><OutputVariables>{self.pout("ENO", en, 1)}{self.pout("Out", o, 2)}</OutputVariables></FbdObject>')
        self.sink(opnd(b), o)
        self.right.append(en)

    def inc(self, a, ins):
        ia = self.lit(opnd(a))
        en_refs = self.refs(ins)
        en, ret, io = self.nid(), self.nid(), self.nid()
        c = f'<Connection refConnectionPointOutId="{ia}"/>'
        pin = PX('<smcext:ConnectionPointInOrder order="2"/>')
        pot = PX('<smcext:ConnectionPointOutOrder order="3"/>')
        self.xml.append(f'<FbdObject xsi:type="Block" typeName="Inc"><InOutVariables><InOutVariable parameterName="InOut"><ConnectionPointIn>{pin}{c}</ConnectionPointIn><ConnectionPointOut connectionPointOutId="{io}">{pot}</ConnectionPointOut></InOutVariable></InOutVariables><InputVariables>{self.pin("EN", en_refs, 1)}</InputVariables><OutputVariables>{self.pout("ENO", en, 1)}{self.pout("", ret, 2)}</OutputVariables></FbdObject>')
        self.sink('', ret)
        self.sink(opnd(a), io)
        self.right.append(en)

    def ton(self, tn, ins):
        name = timers.setdefault(tn, tname.get(f'T{tn:03d}', f'T_{tn:03d}'))
        ipt = self.lit(f'T#{dm.get(tn, 0) * 10}ms')
        in_refs = self.refs(ins)
        q, et = self.nid(), self.nid()
        c = f'<Connection refConnectionPointOutId="{ipt}"/>'
        self.xml.append(f'<FbdObject xsi:type="Block" typeName="TON" instanceName="{name}"><InputVariables>{self.pin("In", in_refs, 1)}{self.pin("PT", c, 2)}</InputVariables><OutputVariables>{self.pout("Q", q, 1)}{self.pout("ET", et, 2)}</OutputVariables></FbdObject>')
        self.sink('', et)
        self.right.append(q)

    def render(self, order):
        left = ''.join(f'<ConnectionPointOut connectionPointOutId="{i}"/>' for i in self.left)
        right = ''.join(f'<ConnectionPointIn><Connection refConnectionPointOutId="{i}"/></ConnectionPointIn>' for i in self.right)
        com = f'<CommonObject xsi:type="Comment"><Content xsi:type="SimpleText">{esc(self.com)}</Content></CommonObject>' if self.com else ''
        return f'<Rung evaluationOrder="{order}">{com}<LdObject xsi:type="LeftPowerRail">{left}</LdObject>{"".join(self.xml)}<LdObject xsi:type="RightPowerRail">{right}</LdObject></Rung>'


def emit(r, e, ins):
    if e[0] == 'c':
        return r.contact(e[1], e[2], e[3], ins)
    if e[0] == 'cmp':
        return r.cmp(e[1], e[2], e[3], ins)
    if e[0] == 'and':
        for x in e[1]:
            ins = emit(r, x, ins)
        return ins
    out = []
    for x in e[1]:
        out += emit(r, x, ins)
    return out


CMP = {'325': '>=', '305': '<>', '310': '<'}


def compile_rung(com, il):
    r = Rung(com)
    stack, cur, base, tr = [], None, ['R'], {}

    def flush():
        nonlocal cur
        if stack:
            assert len(stack) == 1, il
            cur = emit(r, stack.pop(), base)
        return cur

    for line in il:
        p = line.split()
        op, arg = p[0], p[1:]
        m = re.fullmatch(r'(LD|AND|OR)[<>=]+\((\d+)\)', op)
        x = None
        if m:
            head, x = m[1], ('cmp', CMP[m[2]], arg[0], arg[1])
        elif op.lstrip('@') in ('LD', 'LDNOT', 'AND', 'ANDNOT', 'OR', 'ORNOT'):
            bare = op.lstrip('@')
            head = 'LD' if bare.startswith('LD') else 'OR' if bare.startswith('OR') else 'AND'
            if not arg[0].startswith('TR'):
                x = ('c', arg[0], bare.endswith('NOT'), 'rising' if op.startswith('@') else None)
        else:
            head = op
        if head == 'LD':
            if arg[0].startswith('TR'):
                base, cur = list(tr[arg[0]]), None
                continue
            if not stack:
                cur = None
                base = ['R']
            stack.append(x)
        elif head == 'AND':
            if not stack:  # continua dopo OUT TR o dopo LD TR
                base = cur if cur is not None else base
                cur = None
                stack.append(x)
            else:
                a = stack.pop()
                stack.append(('and', (a[1] if a[0] == 'and' else [a]) + [x]))
        elif head == 'OR':
            a = stack.pop()
            stack.append(('or', (a[1] if a[0] == 'or' else [a]) + [x]))
        elif head == 'ANDLD':
            b, a = stack.pop(), stack.pop()
            stack.append(('and', [a, b]))
        elif head == 'ORLD':
            b, a = stack.pop(), stack.pop()
            stack.append(('or', [a, b]))
        elif head == 'OUT' and arg[0].startswith('TR'):
            flush()
            tr[arg[0]] = list(cur)
        elif head == 'OUT':
            flush()
            r.coil(arg[0], None, cur)
        elif head == 'SET':
            flush()
            r.coil(arg[0], 'set', cur)
        elif head == 'RSET':
            flush()
            r.coil(arg[0], 'reset', cur)
        elif head == 'MOV(021)':
            flush()
            r.move(arg[0], arg[1], cur)
        elif head == '++(590)':
            flush()
            r.inc(arg[0], cur)
        elif head == 'TIMHX(551)':
            flush()
            r.ton(int(arg[0]), cur)
        else:
            raise ValueError(line)
    return r


# --- lettura sezioni/reti
sections = []
for s in re.split(r'\n\s+Sec\[\d+\]:=', t)[1:]:
    sname = re.search(r'SecName:="([^"]*)"', s).group(1)
    pending, rungs = '', []
    for rr in re.split(r'\n\s+R\[\d+\]:=', s)[1:]:
        c = re.search(r'Com:=\s*(?:\$\?St\$Bk\?_#\[\d+\]\n(.*?)\$\?St\$Bk|"(.*?)")', rr, re.S)
        com = ' '.join(((c.group(1) or c.group(2) or '') if c else '').split())
        m = re.search(r'SL:=\s*\$\?St\$Bk\?_#\[\d+\]\n(.*?)\$\?St\$Bk', rr, re.S)
        il = [l.strip() for l in m.group(1).splitlines() if l.strip() and not l.startswith("'")] if m else []
        if il and il[0].split()[0] in ('NOP(000)', 'END(001)'):
            pending = (pending + ' - ' + com).strip(' -') if com else pending
            continue
        if not il:
            continue
        if il[0] == 'LD P_Off':  # segnaposto; se e' LD P_Off / OR X resta X
            if il[1].split()[0] != 'OR':
                pending = ''
                continue
            il = ['LD ' + il[1].split()[1]] + il[2:]
        extra = None
        if 'LD ResetGen' in il and '@ANDNOT ResetGen' in il:
            # @ANDNOT letto come "vero tranne che nello scan di salita": da confermare sulla macchina
            il = ['AND ResetGen_Prec' if l == '@ANDNOT ResetGen' else l for l in il]
            extra = ['LD ResetGen', 'OUT ResetGen_Prec']
        rungs.append(((pending + ' - ' + com).strip(' -') if pending else com, il))
        pending = ''
        if extra:
            rungs.append(('Memoria ResetGen allo scan precedente (sostituisce @ANDNOT ResetGen del CX)', extra))
    if rungs:
        sections.append(('S' + sname.lstrip('_'), rungs))

syms['ResetGen_Prec'] = dict(name='ResetGen_Prec', addr='', type='BOOL', com='ResetGen allo scan precedente')
body = []
for i, (n, rungs) in enumerate(sections, 1):
    rx = [compile_rung(c, il).render(j) for j, (c, il) in enumerate(rungs, 1)]
    body.append(f'<BodyContent xsi:type="smcext:LdSection" name="{esc(n)}" evaluationOrder="{i}">{"".join(rx)}</BodyContent>')
body = ''.join(body)


# --- dichiarazioni
def ty(s):
    return 'Un_WordBit' if s['addr'] in bitword else s['type']


def retained(s):
    return s['addr'].startswith('H') or s['addr'] in ('D100', 'D102')


def bit_comments(w):
    its = [(int(s['addr'].split('.')[1]), s) for s in syms.values() if s['addr'].startswith(w['addr'] + '.') and s['com']]
    if not its:
        return ''
    e = ''.join(f'<smcext:ElementComment element="bit[{b}]"><smcext:Text id="1">{esc(s["name"] + " - " + s["com"])}</smcext:Text></smcext:ElementComment>' for b, s in sorted(its, key=lambda x: x[0]))
    return PX(f'<smcext:VariableComment>{e}</smcext:VariableComment>')


def var(s, ext=False):
    doc = f'<Documentation xsi:type="SimpleText">{esc(s["com"])}</Documentation>' if s['com'] else ''
    add = bit_comments(s) if s['addr'] in bitword and not ext else ''
    at = io_at(s['addr']) if s['addr'] and not ext else None
    addr = f'<Address address="{at}"/>' if at else ''
    return f'<Variable name="{s["name"]}">{doc}{add}<Type><TypeName>{ty(s)}</TypeName></Type>{addr}</Variable>'


gl = sorted((syms[n] for n in used), key=lambda s: s['name'])
ext = ''.join(var(s, True) for s in gl)


def loc(n):
    com = syms.get(timers[n], {}).get('com', '')
    doc = f'<Documentation xsi:type="SimpleText">{esc(com)}</Documentation>' if com else ''
    return f'<Variable name="{timers[n]}">{doc}<Type><TypeName>TON</TypeName></Type></Variable>'


locs = ''.join(loc(n) for n in sorted(timers))
globals_r = ''.join(var(s) for s in gl if retained(s))
globals_n = ''.join(var(s) for s in gl if not retained(s))
device = PX('<smcext:DeviceInfo modelName="NX1P2-9B40DT1" version="1.64"/>')
xml = f'''<?xml version="1.0"?>
<Project xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:smcext="https://www.ia.omron.com/Smc" xsi:schemaLocation="https://www.ia.omron.com/Smc IEC61131_10_Ed1_0_SmcExt1_0_Spc1_0.xsd" schemaVersion="1" xmlns="www.iec.ch/public/TC65SC65BWG7TF10">
<FileHeader companyName="OMRON Corporation" productName="Sysmac Studio" productVersion="1.61.0.0"/>
<ContentHeader name="00380" creationDateTime="2026-11-03T09:00:00"><AddDataInfo><Info name="{SMC}" vendor="https://www.ia.omron.com/Smc"/></AddDataInfo>{device}</ContentHeader>
<Types><GlobalNamespace>
<DataTypeDecl name="Un_WordBit"><UserDefinedTypeSpec xsi:type="StructTypeSpec" overlap="true"><Member name="W"><Type><TypeName>WORD</TypeName></Type></Member><Member name="bit"><Type><TypeName>ARRAY[0..15] OF BOOL</TypeName></Type></Member></UserDefinedTypeSpec></DataTypeDecl>
<Program name="Program0">
<ExternalVars>{ext}</ExternalVars>
<Vars accessSpecifier="private">{locs}</Vars>
<MainBody>{body}</MainBody>
</Program>
</GlobalNamespace></Types>
<Instances><Configuration name="ConfigurationName"><Resource name="ResourceName" resourceTypeName="">
<GlobalVars retain="true">{globals_r}</GlobalVars>
<GlobalVars>{globals_n}</GlobalVars>
</Resource></Configuration></Instances>
</Project>
'''
open(dst, 'w', encoding='utf-8').write(xml)

# self-check: XML ben formato e ogni connessione ha la sua uscita
root = ET.fromstring(xml)
ns = '{www.iec.ch/public/TC65SC65BWG7TF10}'
nr = 0
for rung in root.iter(ns + 'Rung'):
    nr += 1
    outs = {e.get('connectionPointOutId') for e in rung.iter(ns + 'ConnectionPointOut')}
    refs = {e.get('refConnectionPointOutId') for e in rung.iter(ns + 'Connection')}
    assert refs <= outs, (nr, refs - outs)
miss = [v for v in timers.values() if f'instanceName="{v}"' not in body]
assert not miss, miss
print('sezioni', len(sections), 'reti', nr, 'globali', len(gl), 'timer', len(timers))
for n, rungs in sections:
    print(' ', n, len(rungs))
print('preset ms', {timers[n]: dm.get(n, 0) * 10 for n in sorted(timers)})
print('I/O', sum(1 for s in gl if s['addr'] and io_at(s['addr'])))
