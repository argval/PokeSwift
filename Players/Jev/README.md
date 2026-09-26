# Jev player

External player for the shipped PokeSwift Red corridor (through the Cascade Badge). It posts one button at a time to PokeMac on port 9777 and waits until the telemetry snapshot changes and `inputReady` is true.

Code owns the route, pathfinding, and button presses. Jev is called only for a residual catch, an unspecified yes/no prompt, or a move choice when the battle preference is `super_effective` or `adaptive` and more than one move qualifies. The API key is read from `TYPESAFE_API_KEY`, which can come from the shell or from a local `Players/Jev/.env` (see `.env.example`). Existing shell exports win over `.env`.

```bash
cp .env.example .env
# edit .env and set TYPESAFE_API_KEY
python3 -m jev_player --policy policy.json --trace /tmp/jev-trace.jsonl
```

Run that from `Players/Jev` after `./scripts/launch_app.sh`. Set `objective` in `policy.json` to `oaks_lab` or `rival` for the scripted checkpoints, or leave it on `misty` to stop when `EVENT_BEAT_MISTY` is set.

Unit tests use fixture snapshots and do not start the app or the network:

```bash
python3 -m unittest discover -s tests
```
