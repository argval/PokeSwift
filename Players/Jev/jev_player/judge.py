"""Jev judgments. One request, several questions. Code still owns the buttons."""

from __future__ import annotations


THREAT_LEVELS = (
    "the lead can win comfortably",
    "the fight is even",
    "the lead is likely to faint",
)


class Judge:
    def __init__(self, caller=None, confidence_floor=0.45, noul_threshold=0.6):
        self.caller = caller
        self.confidence_floor = confidence_floor
        self.noul_threshold = noul_threshold

    def ask(self, state, questions):
        if not questions:
            return {}
        if self.caller is not None:
            raw = self.caller(state, questions)
        else:
            raw = self._call_typesafe(state, questions)
        return self._normalize(raw, questions)

    def _call_typesafe(self, state, questions):
        from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

        built = {}
        for key, spec in questions.items():
            kind = spec["kind"]
            if kind == "choice":
                built[key] = Choice(
                    instructions=spec["instructions"],
                    criteria={option: None for option in spec["options"]},
                )
            elif kind == "noul":
                built[key] = Noul(instructions=spec["instructions"])
            elif kind == "score":
                built[key] = Score(instructions=spec["instructions"], criteria=list(spec["criteria"]))
            else:
                raise ValueError(f"unknown Jev question kind: {kind}")
        with TypeSafeClient() as client:
            response = client.system_one(state=state, questions=built)
        raw = {"choices": {}, "nouls": {}, "scores": {}}
        for key, spec in questions.items():
            if spec["kind"] == "choice":
                item = response.choices[key]
                raw["choices"][key] = {
                    "choice": item.choice,
                    "confidence": getattr(item, "confidence", 1.0),
                }
            elif spec["kind"] == "noul":
                item = response.nouls[key]
                raw["nouls"][key] = {"noul": item.noul}
            else:
                item = response.scores[key]
                raw["scores"][key] = {
                    "score": item.score,
                    "confidence": getattr(item, "confidence", 1.0),
                }
        return raw

    def _normalize(self, raw, questions):
        parsed = {}
        for key, spec in questions.items():
            if spec["kind"] == "choice":
                payload = (raw.get("choices") or {}).get(key) or {}
                if not isinstance(payload, dict):
                    payload = {"choice": payload, "confidence": 1.0}
                confidence = float(payload.get("confidence", 1.0))
                parsed[key] = {
                    "kind": "choice",
                    "value": payload.get("choice"),
                    "confidence": confidence,
                    "low_confidence": confidence < self.confidence_floor,
                }
            elif spec["kind"] == "noul":
                payload = (raw.get("nouls") or {}).get(key) or {}
                if not isinstance(payload, dict):
                    payload = {"noul": payload}
                noul = float(payload.get("noul", 0.0))
                certainty = abs(noul - 0.5) * 2
                parsed[key] = {
                    "kind": "noul",
                    "value": noul,
                    "confidence": certainty,
                    "accept": noul >= self.noul_threshold and certainty >= self.confidence_floor,
                    "low_confidence": certainty < self.confidence_floor,
                }
            else:
                payload = (raw.get("scores") or {}).get(key) or {}
                if not isinstance(payload, dict):
                    payload = {"score": payload, "confidence": 1.0}
                confidence = float(payload.get("confidence", 1.0))
                parsed[key] = {
                    "kind": "score",
                    "value": payload.get("score"),
                    "confidence": confidence,
                    "low_confidence": confidence < self.confidence_floor,
                }
        return parsed
