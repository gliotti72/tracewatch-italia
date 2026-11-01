# TraceWatch Italia 0.1.0

Prototipo add-on locale per Home Assistant OS (Raspberry Pi 4 aarch64).

## Funzioni
- Acquisizione configurabile dei percorsi verso 1.1.1.1 e 8.8.8.8.
- Stop manuale e passaggio automatico alla sorveglianza.
- Riacquisizione manuale; storico eventi conservato (ultimi 500 eventi).
- Confronto ogni 300 secondi per impostazione predefinita.
- Dashboard tramite Home Assistant Ingress.

## Installazione
Questo ZIP **non è un URL repository** e non può essere inserito nel campo Archivi digitali.
Per installarlo, pubblicare la cartella `tracewatch_repo` in un repository GitHub e aggiungere l'URL GitHub in Home Assistant > Impostazioni > Applicazioni > Installa app > Archivi digitali. In alternativa copiare i file su un percorso locale add-on accessibile al Supervisor.

## Limiti e sicurezza
- Non effettua WHOIS/RDAP, notifiche push, comandi MikroTik o blocchi automatici.
- I cambiamenti traceroute sono indizi, non prove di attacco o intercettazione.
- Gli hop che non rispondono possono produrre falsi positivi.
- La sorveglianza rileva ogni percorso non incluso nei campioni di acquisizione; può generare più eventi ripetuti.
- Non è stato ancora collaudato su un Raspberry reale; usare inizialmente per osservazione.
