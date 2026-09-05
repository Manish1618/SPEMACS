"""The investigation Copilot: dynamic query planning over the retrieval toolset.

The question is never matched against a template. The planner is handed the full
tool catalogue and decides, per question, which tools to call and with which
arguments; the sequence it chooses is recorded and returned as the query plan, so
an investigator can see how an answer was reached.

Grounding is enforced rather than requested. After the model composes an answer,
every citation, entity reference and visual action it emitted is checked against
what the tools actually returned. Anything the model invented is removed and
recorded, and if a claimed citation cannot be resolved the answer's confidence is
lowered accordingly.

There are two planners. The model-driven one is primary. The deterministic one
runs when no key is configured or the API call fails; it extracts entities,
times and question structure from the text and builds a plan from those
features. It is weaker on unusual phrasings and says so in its own output.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.services import retrieval
from app.services.llm import GeminiProvider, LLMUnavailable, ToolCall, get_provider
from app.services.retrieval import AccessContext

MAX_TOOL_ROUNDS = 8
MAX_RECORDS_TO_MODEL = 14


SYSTEM_INSTRUCTION = """\
You are the investigation assistant inside SPEMASS, a decision-support platform used by
authorised investigators. You answer questions by calling the retrieval tools you have been
given and reporting what they return.

HOW TO WORK

Decide for yourself which tools to call and in what order. Chain them: resolve a name to an
entity id before using that id, find an event before filtering relationships by its time, and
so on. Call several tools when a question needs several kinds of material. If a first attempt
returns nothing, try a different tool or a broader filter before concluding the data is absent.

Before stating any significant conclusion, call find_contradictions. Actively looking for
material that cuts against your reading is part of the job, not an optional extra.

WHAT YOU MAY SAY

Every factual statement must come from a tool result in this conversation. If the tools did not
return it, you do not know it. Never fill a gap with general knowledge or plausible inference
presented as fact.

Distinguish these clearly and never blur them:
  - an observed record ("the toll reader logged the vehicle at 18:40")
  - what a source asserts ("the witness statement says he was in Dubai")
  - your own analytical reading ("these two records cannot both be accurate")
  - an unknown ("no subscriber has been established for this handset")

If the tools returned too little to answer, say so plainly and list what is missing. An honest
"the available records do not establish this" is a correct answer. Do not pad it.

If the question could reasonably mean two different things, or a name resolves to several
entities with similar confidence, ask which is meant instead of guessing.

WHAT YOU MUST NOT DO

You do not determine guilt or innocence, recommend arrest, charge or punishment, or assert
criminal intent. You do not infer wrongdoing from association, from being in the same place as
someone, or from a person's position in a network. Structural prominence in a graph means the
records place someone at a well-connected point; it means nothing else. An anomaly is a
deviation from a baseline, which is a reason to look further, not a finding.

Where an entity is a person, write about what the records show, not about what kind of person
they are. The investigator decides what any of it means.

STYLE

Write for a professional reader in plain prose. Be specific: name dates, places, amounts and
record types. Prefer short paragraphs over lists of adjectives. Do not open with a restatement
of the question, and do not close with a summary of what you just said. No exclamation marks,
no dramatic language, no speculation dressed as caution."""


FINAL_SCHEMA_INSTRUCTION = """\
Now produce your final answer as a single JSON object with exactly these keys:

  "answer"                 string. The answer in prose, following the style rules.
  "confidence"             one of "HIGH", "MEDIUM", "LOW", "INSUFFICIENT_EVIDENCE",
                           "NEEDS_CLARIFICATION".
  "confidence_reason"      string. One sentence on what drives that level.
  "requires_clarification" boolean.
  "clarification_options"  array of strings. Non-empty only when asking for clarification.
  "citations"              array of objects, each:
                             {"evidence_id": string or null,
                              "document_id": string or null,
                              "event_ids": array of strings,
                              "source_title": string,
                              "supports": string  (the specific claim this backs)}
                           Only ids that appeared in tool results. Never invent one.
  "contradictions"         array of objects: {"summary": string, "source": string}
  "limitations"            array of strings. What this answer cannot establish and why.
  "next_steps"             array of strings. Concrete investigative actions.
  "entities"               array of entity ids referenced, all from tool results.
  "visual_actions"         array of objects, each one of:
                             {"action": "FOCUS_GRAPH_NODES", "entity_ids": [...], "label": string}
                             {"action": "FILTER_MAP", "event_ids": [...], "label": string}
                             {"action": "FOCUS_TIMELINE", "start": ISO8601, "end": ISO8601,
                              "label": string}
                             {"action": "SHOW_EVIDENCE", "evidence_ids": [...], "label": string}
                           Include the views that would genuinely help with this question.

Return the JSON object only."""


# ---------------------------------------------------------------------------
# Conversation memory
# ---------------------------------------------------------------------------

@dataclass
class ConversationState:
    """What "it", "that one" and "the second" refer to.

    Carried between turns so follow-up questions resolve without the investigator
    having to restate the subject.
    """

    conversation_id: str
    case_id: str
    focus_entities: List[Dict[str, str]] = field(default_factory=list)
    last_result_set: List[Dict[str, Any]] = field(default_factory=list)
    last_result_kind: str = ""
    time_window: Optional[Tuple[str, str]] = None
    evidence_in_play: List[str] = field(default_factory=list)
    turns: int = 0

    def describe(self) -> str:
        """Rendered into the prompt so the model can resolve references itself."""
        if not (self.focus_entities or self.last_result_set or self.time_window):
            return ""

        lines = ["CONTEXT CARRIED FROM EARLIER IN THIS CONVERSATION"]
        if self.focus_entities:
            named = ", ".join(
                f"{e['label']} ({e['entity_id']})" for e in self.focus_entities[:8]
            )
            lines.append(f"Entities currently in focus: {named}.")
        if self.time_window:
            lines.append(f"Time window in focus: {self.time_window[0]} to {self.time_window[1]}.")
        if self.evidence_in_play:
            lines.append(f"Evidence in play: {', '.join(self.evidence_in_play[:10])}.")
        if self.last_result_set:
            lines.append(
                f"The previous answer presented this ordered list of {self.last_result_kind}. "
                "An ordinal reference such as \"the second one\" means the corresponding item:"
            )
            for index, item in enumerate(self.last_result_set[:10], start=1):
                lines.append(f"  {index}. {item.get('summary', json.dumps(item)[:160])}")
        return "\n".join(lines)


class SessionStore:
    """In-process conversation memory, capped so a long-running server cannot grow without bound."""

    def __init__(self, capacity: int = 200):
        self._states: Dict[str, ConversationState] = {}
        self._capacity = capacity

    def get(self, conversation_id: str, case_id: str) -> ConversationState:
        state = self._states.get(conversation_id)
        if state is None or state.case_id != case_id:
            state = ConversationState(conversation_id=conversation_id, case_id=case_id)
            if len(self._states) >= self._capacity:
                self._states.pop(next(iter(self._states)))
            self._states[conversation_id] = state
        return state

    def reset(self, conversation_id: str) -> None:
        self._states.pop(conversation_id, None)


sessions = SessionStore()


# ---------------------------------------------------------------------------
# Plan trace
# ---------------------------------------------------------------------------

@dataclass
class PlanStep:
    step: int
    tool: str
    arguments: Dict[str, Any]
    record_count: int
    outcome: str


def _compact(result: Dict[str, Any]) -> Dict[str, Any]:
    """Trim a tool result before returning it to the model.

    Large result sets are truncated rather than dropped, and the true total is
    reported so the model does not mistake a truncated page for the whole answer.
    """
    compacted = dict(result)
    records = result.get("records") or []
    if len(records) > MAX_RECORDS_TO_MODEL:
        compacted["records"] = records[:MAX_RECORDS_TO_MODEL]
        compacted["records_truncated"] = True
        compacted["records_total"] = len(records)
        compacted["truncation_note"] = (
            f"{len(records)} records matched; the first {MAX_RECORDS_TO_MODEL} are shown. "
            "Narrow the filters if you need the rest."
        )
    return compacted


# ---------------------------------------------------------------------------
# Grounding checks
# ---------------------------------------------------------------------------

class GroundingIndex:
    """Everything the tools actually returned, for checking the answer against."""

    def __init__(self) -> None:
        self.evidence_ids: set = set()
        self.document_ids: set = set()
        self.event_ids: set = set()
        self.entity_ids: set = set()
        self.entity_labels: Dict[str, str] = {}
        self.total_records = 0

    def absorb(self, result: Dict[str, Any]) -> None:
        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in ("evidence_id",) and isinstance(value, str):
                        self.evidence_ids.add(value)
                    elif key == "evidence_ids" and isinstance(value, list):
                        self.evidence_ids.update(v for v in value if isinstance(v, str))
                    elif key == "document_id" and isinstance(value, str):
                        self.document_ids.add(value)
                    elif key == "event_id" and isinstance(value, str):
                        self.event_ids.add(value)
                    elif key in ("entity_id", "source_id", "target_id", "centre") and isinstance(value, str):
                        self.entity_ids.add(value)
                    elif key == "related_entities" and isinstance(value, list):
                        self.entity_ids.update(v for v in value if isinstance(v, str))
                    elif key == "entities" and isinstance(value, list):
                        self.entity_ids.update(v for v in value if isinstance(v, str))
                    walk(value)
                if "entity_id" in node and "label" in node:
                    if isinstance(node["entity_id"], str) and isinstance(node["label"], str):
                        self.entity_labels[node["entity_id"]] = node["label"]
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(result)
        self.total_records += len(result.get("records") or [])


# Assertions of criminal responsibility. The system supports investigative
# decisions and does not reach them, so an answer containing these is withheld.
_PROHIBITED = re.compile(
    r"\b(is guilty|are guilty|is a criminal|is the culprit|is innocent|proves guilt|"
    r"should be arrested|recommend arrest|must be charged|should be prosecuted|"
    r"beyond reasonable doubt|is the mastermind|is laundering|is a fraudster)\b",
    re.IGNORECASE,
)

# Characterisations of a person's honesty. Establishing that records contradict an
# account is legitimate analysis; concluding that the person lied is a credibility
# finding for the investigator, not the system. These are corrected in place
# rather than withheld, since the underlying observation is sound.
_CREDIBILITY = re.compile(
    r"\b(falsely claimed|falsely stated|lied|is lying|was lying|fabricated|"
    r"deliberately misled|knowingly false)\b",
    re.IGNORECASE,
)

_CREDIBILITY_REPLACEMENTS = {
    "falsely claimed": "stated",
    "falsely stated": "stated",
    "lied": "gave an account contradicted by the records",
    "is lying": "gives an account contradicted by the records",
    "was lying": "gave an account contradicted by the records",
    "fabricated": "gave an account not supported by",
    "deliberately misled": "gave an account contradicted by the records",
    "knowingly false": "contradicted by the records",
}


def _check_language(answer: str) -> List[str]:
    return sorted({m.group(0).lower() for m in _PROHIBITED.finditer(answer or "")})


def _soften_credibility(answer: str) -> Tuple[str, List[str]]:
    """Replace claims about a person's honesty with claims about the records."""
    found = sorted({m.group(0).lower() for m in _CREDIBILITY.finditer(answer or "")})
    if not found:
        return answer, []

    def swap(match: re.Match) -> str:
        return _CREDIBILITY_REPLACEMENTS.get(match.group(0).lower(), match.group(0))

    return _CREDIBILITY.sub(swap, answer), found


def _validate(
    payload: Dict[str, Any],
    index: GroundingIndex,
    known_evidence: Optional[set] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Strip anything the model asserted that the tools did not return.

    known_evidence is the set of ids actually present in the evidence register. An
    id can appear in a relationship's evidence list without a corresponding
    exhibit having been registered; a citation to one of those is a dangling
    reference and is reported rather than presented as a source.
    """
    notes: List[str] = []

    kept_citations = []
    for citation in payload.get("citations") or []:
        if not isinstance(citation, dict):
            continue
        evidence_id = citation.get("evidence_id")
        document_id = citation.get("document_id")
        event_ids = [e for e in (citation.get("event_ids") or []) if isinstance(e, str)]

        resolved_evidence = evidence_id if evidence_id in index.evidence_ids else None
        resolved_document = document_id if document_id in index.document_ids else None
        resolved_events = [e for e in event_ids if e in index.event_ids]

        if evidence_id and not resolved_evidence:
            notes.append(
                f"Citation to {evidence_id} was removed: no such evidence id appeared in the "
                "retrieved records."
            )
        elif (
            resolved_evidence
            and known_evidence is not None
            and resolved_evidence not in known_evidence
        ):
            # The id is referenced by the data but no exhibit has been registered
            # under it, so it cannot be opened or re-verified.
            notes.append(
                f"Citation to {resolved_evidence} was removed: the id is referenced in the "
                "records but no evidence artifact has been registered under it."
            )
            resolved_evidence = None
        if document_id and not resolved_document:
            notes.append(
                f"Citation to document {document_id} was removed: it did not appear in the "
                "retrieved records."
            )

        if not (resolved_evidence or resolved_document or resolved_events):
            continue

        citation["evidence_id"] = resolved_evidence
        citation["document_id"] = resolved_document
        citation["event_ids"] = resolved_events
        kept_citations.append(citation)
    payload["citations"] = kept_citations

    entities = [e for e in (payload.get("entities") or []) if e in index.entity_ids]
    payload["entities"] = entities

    kept_actions = []
    for action in payload.get("visual_actions") or []:
        if not isinstance(action, dict):
            continue
        kind = action.get("action")
        if kind == "FOCUS_GRAPH_NODES":
            ids = [i for i in (action.get("entity_ids") or []) if i in index.entity_ids]
            if not ids:
                continue
            action["entity_ids"] = ids
        elif kind == "FILTER_MAP":
            ids = [i for i in (action.get("event_ids") or []) if i in index.event_ids]
            if not ids:
                continue
            action["event_ids"] = ids
        elif kind == "SHOW_EVIDENCE":
            ids = [i for i in (action.get("evidence_ids") or []) if i in index.evidence_ids]
            if not ids:
                continue
            action["evidence_ids"] = ids
        elif kind == "FOCUS_TIMELINE":
            if not (action.get("start") and action.get("end")):
                continue
        else:
            continue
        kept_actions.append(action)
    payload["visual_actions"] = kept_actions

    softened, credibility_terms = _soften_credibility(payload.get("answer", ""))
    if credibility_terms:
        payload["answer"] = softened
        notes.append(
            "Wording characterising a person's honesty ("
            + ", ".join(credibility_terms)
            + ") was rewritten to describe the conflict between the account and the records. "
            "Whether an account was untruthful is a judgement for the investigator."
        )

    flagged = _check_language(payload.get("answer", ""))
    if flagged:
        notes.append(
            "The drafted answer used language asserting a criminal conclusion "
            f"({', '.join(flagged)}). SPEMASS supports investigative decisions and does not "
            "reach them, so the answer has been withheld and must be re-examined."
        )
        payload["answer"] = (
            "The drafted answer was withheld because it stated a conclusion about criminal "
            "responsibility, which this system does not do. Ask the question again in terms of "
            "what the records show, and the underlying material will be presented for you to "
            "assess."
        )
        payload["confidence"] = "LOW"

    if index.total_records == 0 and payload.get("confidence") not in (
        "INSUFFICIENT_EVIDENCE",
        "NEEDS_CLARIFICATION",
    ):
        payload["confidence"] = "INSUFFICIENT_EVIDENCE"
        notes.append(
            "No tool returned any record, so confidence was lowered to insufficient evidence."
        )

    if not payload.get("citations") and payload.get("confidence") == "HIGH":
        payload["confidence"] = "MEDIUM"
        notes.append(
            "Confidence was lowered from high because the answer carries no resolvable citation."
        )

    return payload, notes


# ---------------------------------------------------------------------------
# Deterministic fallback planner
# ---------------------------------------------------------------------------

_MONTHS = (
    "january february march april may june july august september october november december"
).split()

_SIGNALS = {
    "connection": r"\b(connect|connected|connection|link|linked|relationship|related|between|tie|associate)\b",
    "path": r"\b(how are|path|route|chain|via|through)\b",
    "location": r"\b(where|location|place|located|whereabouts|seen|present)\b",
    "temporal": r"\b(when|before|after|during|between|since|until|timeline|changed|evolve)\b",
    "communication": r"\b(call|called|calls|communicat|contact|phone|spoke|talked)\b",
    "financial": r"\b(transaction|transfer|payment|money|funds|paid|account|wire|remit)\b",
    "anomaly": r"\b(unusual|anomal|strange|odd|irregular|suspicious|spike|surge|deviat|stands out)\b",
    "contradiction": r"\b(contradict|conflict|inconsisten|challenge|refute|dispute|against|disprove)\b",
    "evidence": r"\b(evidence|support|prove|proof|corroborat|basis|back(s|ed)? up)\b",
    "integrity": r"\b(integrity|tamper|modified|altered|hash|chain of custody|custody|unchanged)\b",
    "osint": r"\b(osint|public|open source|news|registry|external|internet)\b",
    "crosscase": r"\b(cross.case|other case|both cases|multiple cases|another investigation)\b",
    "compare": r"\b(compare|comparison|versus|vs\.?|difference between)\b",
    "network": r"\b(central|centrality|hub|network|cluster|community|important|bridge|structure)\b",
    "summary": r"\b(summar|overview|everything|tell me about|what do we know|brief)\b",
    "gaps": r"\b(missing|gap|unknown|don't know|do not know|what else|incomplete)\b",
    "duplicate": r"\b(duplicate|same person|resolve|merge|alias)\b",
    "hypothesis": r"\b(hypothes|theory|h1|h2|hyp-)\b",
}


def _extract_candidates(question: str) -> List[str]:
    """Pull probable entity mentions out of free text."""
    candidates: List[str] = []
    candidates += re.findall(r"\"([^\"]{2,60})\"", question)
    candidates += re.findall(r"\b((?:ENT|EVID|EVT|CASE|DOC|HYP|R)-[A-Z0-9-]+)\b", question)
    candidates += re.findall(r"\b(\+?\d[\d\s-]{7,17}\d)\b", question)
    candidates += re.findall(r"\b([A-Z]{2}-\d{2}-[A-Z]{1,2}-\d{4})\b", question)

    # Capitalised runs, minus sentence-initial words and common leaders.
    stop = {
        "What", "Who", "Where", "When", "Why", "How", "Which", "Show", "Find", "Tell",
        "Compare", "Is", "Are", "Does", "Do", "Did", "Can", "Could", "The", "This", "That",
        "I", "We", "Give", "List", "Has", "Have", "Search", "Summarise", "Summarize",
    }
    for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b", question):
        phrase = match.group(1)
        head = phrase.split()[0]
        if head in stop:
            phrase = " ".join(phrase.split()[1:])
        if len(phrase) > 2 and phrase not in candidates:
            candidates.append(phrase)

    seen, unique = set(), []
    for candidate in candidates:
        cleaned = candidate.strip()
        if cleaned and cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            unique.append(cleaned)
    return unique[:6]


def _extract_time_window(question: str) -> Tuple[Optional[str], Optional[str]]:
    """Interpret an explicit date or a relative period mentioned in the question."""
    lowered = question.lower()

    explicit = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", question)
    if explicit:
        day = datetime(
            int(explicit.group(1)), int(explicit.group(2)), int(explicit.group(3)),
            tzinfo=timezone.utc,
        )
        return day.isoformat(), (day + timedelta(days=1)).isoformat()

    named = re.search(
        r"\b(\d{1,2})\s+(%s)\b(?:\s+(\d{4}))?" % "|".join(_MONTHS), lowered
    ) or re.search(
        r"\b(%s)\s+(\d{1,2})\b(?:,?\s+(\d{4}))?" % "|".join(_MONTHS), lowered
    )
    if named:
        groups = named.groups()
        if groups[0].isdigit():
            day_num, month_name, year = int(groups[0]), groups[1], groups[2]
        else:
            month_name, day_num, year = groups[0], int(groups[1]), groups[2]
        month = _MONTHS.index(month_name) + 1
        day = datetime(int(year) if year else 2024, month, day_num, tzinfo=timezone.utc)
        return day.isoformat(), (day + timedelta(days=1)).isoformat()

    relative = re.search(r"\blast (\d+) (day|week|month)s?\b", lowered)
    if relative:
        count, unit = int(relative.group(1)), relative.group(2)
        days = count * {"day": 1, "week": 7, "month": 30}[unit]
        end = datetime(2024, 2, 29, tzinfo=timezone.utc)  # end of the dataset's coverage
        return (end - timedelta(days=days)).isoformat(), end.isoformat()

    return None, None


class DeterministicPlanner:
    """Fallback planner used when the language model is unavailable.

    Builds a plan from features of the question -- named entities, dates, and the
    kinds of language present -- then reports strictly what the tools returned.
    It is not a lookup table of prepared answers; it composes from retrieved data,
    and it declares its own reduced capability in every answer it produces.
    """

    def run(
        self,
        db: Session,
        ctx: AccessContext,
        question: str,
        state: ConversationState,
        reason: str,
    ) -> Dict[str, Any]:
        plan: List[PlanStep] = []
        index = GroundingIndex()
        results: Dict[str, Dict[str, Any]] = {}
        step_no = 0

        def run_tool(tool: str, **arguments: Any) -> Dict[str, Any]:
            nonlocal step_no
            step_no += 1
            result = retrieval.execute_tool(db, ctx, tool, arguments)
            index.absorb(result)
            count = len(result.get("records") or [])
            plan.append(
                PlanStep(
                    step=step_no,
                    tool=tool,
                    arguments=arguments,
                    record_count=count,
                    outcome=result.get("error") or result.get("note") or f"{count} records",
                )
            )
            results.setdefault(tool, result)
            return result

        signals = {name: bool(re.search(rx, question, re.I)) for name, rx in _SIGNALS.items()}
        case_id = state.case_id
        start_time, end_time = _extract_time_window(question)

        # Resolve whatever the question names; fall back to the conversation focus.
        resolved: List[Dict[str, Any]] = []
        ambiguous: List[Dict[str, Any]] = []
        for candidate in _extract_candidates(question):
            found = run_tool("resolve_entity", query=candidate)
            records = found.get("records") or []
            if not records:
                continue
            if found.get("ambiguous"):
                ambiguous = records[:3]
            resolved.append(records[0])

        if not resolved and state.focus_entities:
            for focus in state.focus_entities[:2]:
                profile = run_tool("get_entity_profile", entity_id=focus["entity_id"])
                if profile.get("records"):
                    resolved.append(profile["records"][0])

        if ambiguous:
            options = [
                f"{r['label']} ({r['entity_type']}, {r['entity_id']})" for r in ambiguous
            ]
            return self._package(
                answer=(
                    "That name matches more than one entity in this case, and the records for each "
                    "are different. Tell me which is meant and I will run the question against it."
                ),
                confidence="NEEDS_CLARIFICATION",
                plan=plan,
                index=index,
                requires_clarification=True,
                clarification_options=options,
                entities=[r["entity_id"] for r in ambiguous],
                reason=reason,
            )

        entity_ids = [r["entity_id"] for r in resolved]

        # Choose tools from the features present in the question.
        if signals["compare"]:
            cases = ctx.allowed_cases
            if len(cases) >= 2:
                run_tool("compare_cases", case_id_a=cases[0], case_id_b=cases[1])
        if signals["crosscase"]:
            run_tool("find_cross_case_entities")
        if signals["path"] or (signals["connection"] and len(entity_ids) >= 2):
            if len(entity_ids) >= 2:
                run_tool("find_paths", source_id=entity_ids[0], target_id=entity_ids[1])
        if signals["connection"] and len(entity_ids) == 1:
            run_tool("get_neighborhood", entity_id=entity_ids[0], hops=1)
        if signals["location"] or signals["temporal"] or signals["communication"] or signals["financial"]:
            args: Dict[str, Any] = {"case_id": case_id}
            if entity_ids:
                args["entity_ids"] = entity_ids
            if start_time:
                args["start_time"], args["end_time"] = start_time, end_time
            if signals["communication"] and not signals["financial"]:
                args["event_types"] = ["CALL"]
            elif signals["financial"] and not signals["communication"]:
                args["event_types"] = ["TRANSACTION"]
            run_tool("find_events", **args)
        if signals["temporal"] and entity_ids and start_time:
            run_tool("find_relationships", entity_ids=entity_ids, first_recorded_after=start_time)
        if signals["anomaly"]:
            run_tool("detect_anomalies", case_id=case_id, **({"entity_ids": entity_ids} if entity_ids else {}))
        if signals["network"]:
            run_tool("graph_analytics", case_id=case_id)
        if signals["contradiction"] or signals["evidence"]:
            run_tool("find_contradictions", case_id=case_id, **({"entity_ids": entity_ids} if entity_ids else {}))
        if signals["integrity"]:
            run_tool("verify_integrity", case_id=case_id)
        if signals["osint"]:
            term = resolved[0]["label"] if resolved else question
            run_tool("osint_lookup", query=term, case_id=case_id,
                     **({"entity_id": entity_ids[0]} if entity_ids else {}))
        if signals["duplicate"]:
            run_tool("find_resolution_candidates", case_id=case_id)
        if signals["hypothesis"]:
            run_tool("get_hypotheses", case_id=case_id)
        if signals["summary"] or signals["gaps"] or not plan[1:]:
            run_tool("summarise_case", case_id=case_id)
            if entity_ids:
                run_tool("get_entity_profile", entity_id=entity_ids[0])
        if signals["evidence"] and entity_ids:
            run_tool("search_documents", query=resolved[0]["label"], case_id=case_id)

        return self._compose(question, plan, results, index, resolved, reason)

    def _compose(
        self,
        question: str,
        plan: List[PlanStep],
        results: Dict[str, Dict[str, Any]],
        index: GroundingIndex,
        resolved: List[Dict[str, Any]],
        reason: str,
    ) -> Dict[str, Any]:
        """Report what the tools returned. No narrative beyond the records."""
        paragraphs: List[str] = []
        citations: List[Dict[str, Any]] = []
        contradictions: List[Dict[str, Any]] = []
        limitations: List[str] = []
        next_steps: List[str] = []
        actions: List[Dict[str, Any]] = []

        if resolved:
            named = ", ".join(f"{r['label']} ({r['entity_type'].lower()})" for r in resolved[:4])
            paragraphs.append(f"The question was matched to these records: {named}.")

        events = (results.get("find_events") or {}).get("records") or []
        if events:
            total = (results.get("find_events") or {}).get("total_matching", len(events))
            first, last = events[0], events[-1]
            kinds = sorted({e["event_type"].lower().replace("_", " ") for e in events})
            paragraphs.append(
                f"{total} recorded events match, covering {', '.join(kinds)}. They run from "
                f"{first['timestamp'][:16].replace('T', ' ')} ({first['title']}) to "
                f"{last['timestamp'][:16].replace('T', ' ')} ({last['title']})."
            )
            for event in events[:6]:
                if event.get("evidence_id"):
                    citations.append(
                        {
                            "evidence_id": event["evidence_id"],
                            "document_id": None,
                            "event_ids": [event["event_id"]],
                            "source_title": event["title"],
                            "supports": event.get("summary", "")[:220],
                        }
                    )
            actions.append(
                {
                    "action": "FILTER_MAP",
                    "event_ids": [e["event_id"] for e in events[:25]],
                    "label": "Show these events on the map",
                }
            )
            actions.append(
                {
                    "action": "FOCUS_TIMELINE",
                    "start": first["timestamp"],
                    "end": last["timestamp"],
                    "label": "Focus the timeline on this period",
                }
            )

        paths = (results.get("find_paths") or {}).get("records") or []
        if paths:
            best = paths[0]
            chain = " then ".join(
                f"{l['source_label']} {l['rel_type'].lower().replace('_', ' ')} {l['target_label']}"
                for l in best["links"]
            )
            paragraphs.append(
                f"The shortest recorded chain between them runs over {best['hop_count']} links: "
                f"{chain}. The weakest link carries a confidence of "
                f"{best['weakest_link_confidence']}, which is the ceiling for the chain as a whole."
            )

        neighborhood = (results.get("get_neighborhood") or {}).get("records") or []
        if neighborhood:
            node_count = len(neighborhood[0]["nodes"]) - 1
            paragraphs.append(
                f"{node_count} entities are directly connected in the recorded relationships."
            )
            actions.append(
                {
                    "action": "FOCUS_GRAPH_NODES",
                    "entity_ids": [n["entity_id"] for n in neighborhood[0]["nodes"][:30]],
                    "label": "Show this part of the network",
                }
            )

        anomalies = (results.get("detect_anomalies") or {}).get("records") or []
        if anomalies:
            paragraphs.append(
                f"{len(anomalies)} deviations from the observed baseline were found. "
                + " ".join(
                    f"{a['anomaly_type'].lower().replace('_', ' ').capitalize()}: {a['observed']}, "
                    f"against a baseline of {a['baseline']} ({a['deviation']})."
                    for a in anomalies[:3]
                )
                + " A deviation indicates where to look and establishes nothing by itself."
            )

        found_contradictions = (results.get("find_contradictions") or {}).get("records") or []
        for item in found_contradictions[:5]:
            contradictions.append(
                {
                    "summary": f"{item['asserted']} {item['assessment']}",
                    "source": (item.get("asserted_source") or {}).get("title", "case records"),
                }
            )

        integrity = results.get("verify_integrity") or {}
        if integrity.get("summary"):
            summary = integrity["summary"]
            paragraphs.append(
                f"Of {summary['checked']} evidence artifacts checked, {summary['verified']} rehash "
                f"to their sealed values and {summary['failed']} do not. The ledger chain is "
                f"{'intact' if integrity.get('ledger', {}).get('chain_valid') else 'broken'}."
            )

        osint = results.get("osint_lookup") or {}
        if osint.get("source_independence"):
            independence = osint["source_independence"]
            paragraphs.append(
                f"Public-source material: {independence['reports_held']} reports are held, tracing "
                f"back to about {independence['likely_independent_sources']} originating sources "
                f"({independence['derivative_reports']} are derivative). Repetition across outlets "
                "is not corroboration."
            )

        analytics = results.get("graph_analytics") or {}
        if analytics.get("records"):
            top = analytics["records"][:3]
            paragraphs.append(
                "By structural position in the recorded network, the most connected entities are "
                + ", ".join(f"{r['label']} (degree {r['degree_centrality']})" for r in top)
                + ". This describes position in the data that has been collected and implies "
                "nothing about conduct."
            )

        case_summary = (results.get("summarise_case") or {}).get("records") or []
        if case_summary:
            summary = case_summary[0]
            paragraphs.append(
                f"{summary['title']} holds {sum(summary['entity_counts'].values())} entities and "
                f"{sum(summary['event_counts'].values())} recorded events between "
                f"{(summary['first_event'] or '')[:10]} and {(summary['last_event'] or '')[:10]}, "
                f"with {summary['evidence_count']} evidence artifacts."
            )
            limitations.extend(summary.get("known_gaps", [])[:4])

        comparison = (results.get("compare_cases") or {}).get("records") or []
        if comparison:
            item = comparison[0]
            paragraphs.append(
                f"{item['case_a']['title']} and {item['case_b']['title']} share "
                f"{item['shared_count']} entities: "
                + ", ".join(e["label"] for e in item["shared_entities"][:6])
                + "."
            )

        candidates = (results.get("find_resolution_candidates") or {}).get("records") or []
        if candidates:
            top = candidates[0]
            paragraphs.append(
                f"{len(candidates)} possible duplicate records were found. The strongest is "
                f"{top['left']['label']} ({top['left']['entity_id']}) against "
                f"{top['right']['label']} ({top['right']['entity_id']}), matching on "
                f"{', '.join(top['matching_attributes']) or 'name similarity alone'}. "
                "Nothing is merged without your confirmation."
            )

        if not paragraphs:
            paragraphs.append(
                "The retrieval tools returned no records for this question within the case you "
                "have open. That means the material has not been collected, not that the answer "
                "is negative."
            )

        limitations.append(
            "This answer was produced by the fallback planner because the language model was "
            f"unavailable ({reason}). It reports what the retrieval tools returned but reads the "
            "question less flexibly than the model does. Rephrasing more explicitly, or naming "
            "entities directly, will give a better result."
        )
        next_steps.append("Re-run the question once the model connection is restored.")

        confidence = "MEDIUM" if index.total_records else "INSUFFICIENT_EVIDENCE"
        return self._package(
            answer="\n\n".join(paragraphs),
            confidence=confidence,
            plan=plan,
            index=index,
            citations=citations,
            contradictions=contradictions,
            limitations=limitations,
            next_steps=next_steps,
            entities=[r["entity_id"] for r in resolved],
            actions=actions,
            reason=reason,
        )

    def _package(
        self,
        answer: str,
        confidence: str,
        plan: List[PlanStep],
        index: GroundingIndex,
        citations: Optional[List[Dict[str, Any]]] = None,
        contradictions: Optional[List[Dict[str, Any]]] = None,
        limitations: Optional[List[str]] = None,
        next_steps: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
        requires_clarification: bool = False,
        clarification_options: Optional[List[str]] = None,
        reason: str = "",
    ) -> Dict[str, Any]:
        return {
            "answer": answer,
            "confidence": confidence,
            "confidence_reason": (
                "Produced by the deterministic fallback planner from retrieved records."
            ),
            "requires_clarification": requires_clarification,
            "clarification_options": clarification_options or [],
            "citations": citations or [],
            "contradictions": contradictions or [],
            "limitations": limitations or [],
            "next_steps": next_steps or [],
            "entities": entities or [],
            "visual_actions": actions or [],
            "query_plan": [asdict(step) for step in plan],
            "planner": "deterministic-fallback",
            "planner_note": f"Language model unavailable: {reason}",
        }


# ---------------------------------------------------------------------------
# Copilot
# ---------------------------------------------------------------------------

class InvestigationCopilot:
    def __init__(self) -> None:
        self.provider: Optional[GeminiProvider] = get_provider()
        self.fallback = DeterministicPlanner()

    def answer(
        self,
        db: Session,
        ctx: AccessContext,
        question: str,
        case_id: str,
        conversation_id: str = "default",
    ) -> Dict[str, Any]:
        state = sessions.get(conversation_id, case_id)
        state.turns += 1

        if self.provider is None:
            payload = self.fallback.run(
                db, ctx, question, state, "no API key is configured"
            )
            self._update_state(db, state, payload)
            return payload

        try:
            payload = self._run_model(db, ctx, question, case_id, state)
        except LLMUnavailable as exc:
            payload = self.fallback.run(db, ctx, question, state, str(exc)[:180])
        except Exception as exc:  # noqa: BLE001 - degrade rather than fail the request
            payload = self.fallback.run(db, ctx, question, state, f"{type(exc).__name__}: {exc}"[:180])

        self._update_state(db, state, payload)
        return payload

    def _run_model(
        self,
        db: Session,
        ctx: AccessContext,
        question: str,
        case_id: str,
        state: ConversationState,
    ) -> Dict[str, Any]:
        index = GroundingIndex()
        plan: List[PlanStep] = []
        declarations = retrieval.tool_declarations()

        preamble = [
            f"Active case: {case_id}.",
            f"Cases this investigator may read: {', '.join(ctx.allowed_cases) or 'none'}.",
            f"Investigator role: {ctx.role}.",
            "Today's date is not relevant; work from the timestamps in the records.",
        ]
        context_block = state.describe()
        if context_block:
            preamble.append(context_block)

        contents: List[Dict[str, Any]] = [
            {
                "role": "user",
                "parts": [{"text": "\n".join(preamble) + f"\n\nQUESTION\n{question}"}],
            }
        ]

        step_no = 0
        for _round in range(MAX_TOOL_ROUNDS):
            turn = self.provider.step(SYSTEM_INSTRUCTION, contents, declarations)

            if not turn.tool_calls:
                break

            # Echo the model's own parts back unchanged. They carry the thought
            # signature the API requires alongside each function call.
            contents.append({"role": "model", "parts": turn.raw_parts})

            response_parts = []
            for call in turn.tool_calls:
                step_no += 1
                result = self._execute(db, ctx, call, case_id)
                index.absorb(result)
                count = len(result.get("records") or [])
                plan.append(
                    PlanStep(
                        step=step_no,
                        tool=call.name,
                        arguments=call.arguments,
                        record_count=count,
                        outcome=result.get("error")
                        or result.get("authorisation")
                        or result.get("note")
                        or f"{count} records",
                    )
                )
                response_parts.append(
                    {
                        "functionResponse": {
                            "name": call.name,
                            "response": _compact(result),
                        }
                    }
                )
            contents.append({"role": "user", "parts": response_parts})

        # Final structured answer, composed only from what the tools returned.
        contents.append({"role": "user", "parts": [{"text": FINAL_SCHEMA_INSTRUCTION}]})
        final = self.provider.step(
            SYSTEM_INSTRUCTION,
            contents,
            tools=[],
            temperature=0.15,
            json_mode=True,
            max_output_tokens=8192,
        )

        from app.services.llm import _loads

        payload = _loads(final.text)
        if payload is None:
            payload = {
                "answer": final.text.strip()
                or "The model did not return a usable answer for this question.",
                "confidence": "LOW",
                "confidence_reason": "The structured response could not be parsed.",
                "requires_clarification": False,
                "clarification_options": [],
                "citations": [],
                "contradictions": [],
                "limitations": ["The answer could not be validated against the retrieved records."],
                "next_steps": [],
                "entities": [],
                "visual_actions": [],
            }

        from app.models.entities import Evidence

        known_evidence = {row.evidence_id for row in db.query(Evidence.evidence_id).all()}
        payload, notes = _validate(payload, index, known_evidence)
        payload["query_plan"] = [asdict(step) for step in plan]
        payload["planner"] = f"model:{self.provider.model}"
        payload["grounding"] = {
            "records_retrieved": index.total_records,
            "tool_calls": len(plan),
            "evidence_available": sorted(index.evidence_ids),
            "validation_notes": notes,
        }
        return payload

    def _execute(
        self, db: Session, ctx: AccessContext, call: ToolCall, case_id: str
    ) -> Dict[str, Any]:
        arguments = dict(call.arguments or {})
        spec = retrieval.TOOLS.get(call.name)
        # Default an omitted case filter to the case the investigator has open,
        # rather than silently widening the search across every readable case.
        if spec and "case_id" in spec.parameters.get("properties", {}):
            arguments.setdefault("case_id", case_id)
        return retrieval.execute_tool(db, ctx, call.name, arguments)

    def _update_state(
        self, db: Session, state: ConversationState, payload: Dict[str, Any]
    ) -> None:
        """Carry forward what a follow-up question might refer to."""
        entities = payload.get("entities") or []
        if entities:
            from app.models.entities import Entity

            rows = db.query(Entity).filter(Entity.entity_id.in_(entities[:8])).all()
            labels = {row.entity_id: row.label for row in rows}
            state.focus_entities = [
                {"entity_id": eid, "label": labels.get(eid, eid)} for eid in entities[:8]
            ]

        evidence = []
        for citation in payload.get("citations") or []:
            if citation.get("evidence_id"):
                evidence.append(citation["evidence_id"])
        if evidence:
            state.evidence_in_play = sorted(set(evidence))[:12]

        for action in payload.get("visual_actions") or []:
            if action.get("action") == "FOCUS_TIMELINE" and action.get("start"):
                state.time_window = (action["start"], action.get("end", action["start"]))

        # Anything the answer enumerated becomes addressable by ordinal next turn.
        enumerated = payload.get("contradictions") or []
        if enumerated:
            state.last_result_kind = "contradictions"
            state.last_result_set = [
                {"summary": item.get("summary", "")[:200]} for item in enumerated
            ]


copilot = InvestigationCopilot()
