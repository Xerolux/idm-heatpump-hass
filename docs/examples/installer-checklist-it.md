# Checklist per l'installatore — IDM Heatpump

Tutto ciò che serve all'integrazione viene attivato al livello installatore del regolatore. Stampa questa pagina e consegnala al tuo installatore.

## 1. Rete

- ☐ Indirizzo IP fisso per il Navigator (prenotazione DHCP o statico) — IP: ____________
- ☐ Navigator e Home Assistant nella stessa rete locale
- ☐ **Nessun** port forwarding per le porte 502, 80 e 61220

## 2. Modbus (obbligatorio)

- ☐ **Gestione edificio (Gebäudeleittechnik) → Modbus TCP → On**
- ☐ Porta TCP: di norma **502**
- ☐ ID slave/unità: di norma **1**
- ☐ L'orologio del regolatore mostra l'ora locale corretta

## 3. FV / GLT (facoltativo)

- ☐ Sorgente segnale FV = **Gestione edificio / Smartfox**
- ☐ Registri di ingresso GLT liberati (74–86: surplus, produzione FV, consumo, batteria, SOC)
- ☐ Nessun altro energy manager scrive gli stessi registri

## 4. Interfaccia web locale (facoltativa)

- ☐ PIN web/rete impostato e consegnato — PIN: ____________
- ☐ Interfaccia web raggiungibile (HTTP 80; Navigator 10 inoltre WebSocket 61220)

## 5. Dati dell'impianto (li legge l'installatore)

| Dato | Valore |
|---|---|
| Generazione Navigator (1.0 / 1.7 / 2.0 / Pro / 10) | ____________ |
| Versione software/firmware | ____________ |
| Numero di schema dell'impianto (es. L7.1) | ____________ |
| Circuiti di riscaldamento attivi (A–G) | ____________ |
| Moduli di zona e ambienti | ____________ |
| Cascata? Numero di unità | ____________ |
| Solare termico / ISC? | ____________ |

L'integrazione **non** richiede: accesso cloud né account myIDM, port forwarding né sblocco dei menu installatore.
