#!/usr/bin/env python3
"""Casi presi dai log reali di Matteo. Servono a impedire che una modifica al
riconoscimento commesse reintroduca i falsi positivi gia' visti (IP, versioni
software, modelli prodotto, pagine HMI, titoli del browser).

    python test_estrazione.py
"""
import sys
from aw_report import estrai_candidati, cliente_plausibile

# (titolo osservato, coppie attese)
CASI = [
    # --- commesse vere, nei vari formati che usa Matteo
    (r"Zilmet347 - TcXaeShell", [("347", "Zilmet")]),
    (r"AffilaturaCastellana354 - TcXaeShell", [("354", "AffilaturaCastellana")]),
    (r"[main] - C:\OMRON\Data\VC\365 - Ergoal - Banco avvitatura rampe - PLC", [("365", "Ergoal")]),
    (r"[main] - C:\OMRON\Data\VC\349-CEB-PallettizzatoreScatole - PLC", [("349", "CEB")]),
    (r"[main] - C:\OMRON\Data\VC\335-HagerLineaMultiprocesso - PLC", [("335", "HagerLineaMultiprocesso")]),
    (r"0175 - Moretto Group s.p.a. - Isola puntatura e saldatura - CPU", [("175", "Moretto Group s.p.a")]),
    (r"342 - Condevo - Banco saldatura perni Y indipendenti - v1.3", [("342", "Condevo")]),
    (r"EasyBuilder Pro V6.10.02.231 : 347_Zilmet_LineaAssemblaggioVasi0.1.cmtp", [("347", "Zilmet")]),

    # --- falsi positivi che NON devono produrre una commessa
    (r"192.168.1.106 - Connessione Desktop remoto", []),
    (r"192.168.250.15 - Connessione Desktop remoto", []),
    (r"EasyBuilder Pro V6.10.01.510 : - [105 - Setup Sistema]", []),
    (r"[main] - C:\OMRON\Data\VC\350-Privius-BancoSaldaturaPerniT450Cerniere", [("350", "Privius")]),
    (r"338 - Inox Veneta - Banco saldatura perni T300 - 2.0.gcf", [("338", "Inox Veneta")]),
    (r"Manuale uso e manutenzione T450 - IT.docx", []),
    (r"Schaffner FN2090-16-06 Filtro antidisturbo di rete 250 V 16 A - Google Chrome", []),
    (r"Inverter Delta 400 V 7.5 kW - Google Chrome", []),
]

# Nomi che il filtro cliente deve rifiutare anche se la forma sembra giusta.
NON_CLIENTI = ["Not Found", "Forbidden", "Authorization Required", "Google Chrome",
               "Cerca con Google", "Setup Sistema", "Preset encoder", "AsseZ",
               "Indirizzi.txt", "QG.pdf", "AnyDesk", "Mozilla Thunderbird",
               "miliardi di anni luce", "GB di RAM"]
CLIENTI = ["Zilmet", "AffilaturaCastellana", "Ergoal", "CEB srl", "Moretto Group s.p.a",
           "Inox Veneta", "Lazzari srl", "Condevo", "Privius", "Hager"]


def main():
    err = 0
    for titolo, atteso in CASI:
        got = [(c, cl) for c, cl in estrai_candidati(titolo) if cliente_plausibile(cl)]
        if got != atteso:
            err += 1
            print(f"FALLITO  {titolo}\n         atteso {atteso}\n         ottenuto {got}")
    for n in NON_CLIENTI:
        if cliente_plausibile(n):
            err += 1
            print(f"FALLITO  '{n}' accettato come cliente")
    for n in CLIENTI:
        if not cliente_plausibile(n):
            err += 1
            print(f"FALLITO  '{n}' rifiutato come cliente")
    tot = len(CASI) + len(NON_CLIENTI) + len(CLIENTI)
    print(f"\n{tot - err}/{tot} casi superati")
    return 1 if err else 0


if __name__ == "__main__":
    sys.exit(main())
