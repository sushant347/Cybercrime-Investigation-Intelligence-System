# Semantic Correction Engine

A **new, independent module** of the Cybercrime Investigation Intelligence System. It sits between the rule-based OCR enhancement (Prompt 2.5) and entity extraction, and uses a **pretrained `xlm-roberta-base`** model for **inference only** to validate rule-proposed OCR corrections in multilingual context. The language model **never generates text** — it only decides whether a candidate word fits its surrounding sentence.

Nothing in the existing pipeline is modified. The engine produces one new field, `semantic_text`, and appends a `semantic_correction` section to the case JSON. `raw_text`, `cleaned_text` and `enhanced_text` remain byte-for-byte unchanged.

## Where it fits (MERGED PIPELINE)

```text
Evidence → PaddleOCR → raw_text
                     → Cleaning        → cleaned_text
                     → Rule Enhancement→ enhanced_text
                     → Semantic Engine → semantic_text     ← THIS MODULE
                     → Entity Extraction (runs on semantic_text)
```

After merge, **entity extraction runs on `semantic_text`**: the semantic
pipeline reuses the existing (unchanged) cleaning-module `EntityExtractor`
via dependency injection and appends the extracted entities to its result
under `semantic_correction.entities`. The cleaning module still extracts
entities from `cleaned_text` into `entities.csv` exactly as before (untouched)
— the merge only *adds* a semantic-text extraction, it removes nothing.

### One-command run (orchestrator)

```bash
python cli.py process CASE_0001            # clean -> enhance -> semantic (+ entities)
python cli.py process CASE_0001 --no-xlmr  # offline heuristic validator
```

`EvidenceProcessingOrchestrator` chains the existing `CleaningService`,
`EnhancementService` and `SemanticCorrectionService` in the correct order; it
delegates to each unchanged service and never reimplements them. The
individual `clean` / `enhance` / `semantic` commands continue to work exactly
as before.

## How correction works (validate, never generate)

```text
enhanced_text
  │
  ├─ EntityProtector        URLs/emails/phones/hashes/… → <URL_1>, <PHONE_2>, …
  ├─ SentenceBuilder        rejoin OCR-broken sentences
  ├─ MixedScriptDetector    flag suspicious tokens (Seवson, Nepव, Go०gle, Aज)
  ├─ CandidateGenerator     propose corrections from the rule resources
  │                         (character-confusion resolver + dictionaries) — RULES, not the LM
  ├─ Validator (Strategy)   XLM-R judges: does the candidate fit the sentence?
  │     ├─ language consistency  (candidate must be single-script)
  │     ├─ dictionary validation
  │     └─ confidence threshold
  ├─ Accept / Reject        only accepted candidates change the text
  └─ EntityProtector.restore originals put back verbatim
        │
        ▼
  semantic_text + corrections[] + accepted/rejected + confidence + statistics
```

Example: OCR `Seवson` → rule candidate `Season` → XLM-R checks whether *Season* fits "Ramesh ko … ticket" → **accept**; otherwise the original `Seवson` is kept. An unsafe or context-incongruent candidate is always rejected.

## Sequence (one `correct()` call)

```text
caller → SemanticCorrectionPipeline.correct(enhanced_text)
       → EntityProtector.protect            → <TYPE_N> placeholders + vault
       → SentenceBuilder.rebuild            → sentences
       → MixedScriptDetector.find           → suspicious tokens
       → for each suspect:
            CandidateGenerator.generate      → rule candidates (no LM)
            build slotted sentence  "… ⁣SLOT⁣ …"
            Validator.validate(slot, original, candidate)
                → XLM-R fill-mask probability of candidate vs original
                → ValidationVerdict(fits, confidence)
            accept if fits AND confidence ≥ threshold AND single-script
       → apply accepted corrections
       → EntityProtector.restore            → semantic_text
       → SemanticResult (+ statistics)
```

## Design (SOLID, DI, Strategy)

The pipeline depends only on the abstract `BaseSemanticValidator`. Two implementations ship:

- `XLMRobertaValidator` — pretrained `xlm-roberta-base` fill-mask, loaded **once** (lazy), GPU if `torch.cuda.is_available()` else CPU. Inference only; no fine-tuning, no training, no dataset.
- `HeuristicSemanticValidator` — dependency-free fallback so the module runs (and its tests pass) with no Transformers/weights, and for offline/air-gapped labs.

Because the validator is injected, **a future fine-tuned model replaces `XLMRobertaValidator` without changing any other file** — that was an explicit design goal.

Every collaborator (entity protector, sentence builder, detector, candidate generator, language detector, validator, threshold) is a constructor parameter, so each is independently testable and replaceable.

## Usage

```python
from backend.modules.evidence.semantic import SemanticCorrectionPipeline

# XLM-R if available, heuristic fallback otherwise
result = SemanticCorrectionPipeline().correct(enhanced_text)
print(result.semantic_text)
for c in result.accepted_corrections:
    print(c.original, "→", c.candidate, c.confidence)
```

```bash
python cli.py semantic CASE_0001                 # whole case (XLM-R if installed)
python cli.py semantic CASE_0001 --evidence EVID_00002
python cli.py semantic CASE_0001 --no-xlmr        # force offline heuristic validator
```

```python
# Inject a custom / future fine-tuned validator without touching the pipeline
from backend.modules.evidence.semantic import SemanticCorrectionPipeline
pipeline = SemanticCorrectionPipeline(validator=MyFineTunedValidator())
```

## Output contract (`semantic_correction` section)

`case_id, evidence_id, enhanced_text (verbatim), semantic_text, corrections[] {original, candidate, accepted, confidence, validator, candidate_source, reason, language}, accepted_corrections[], rejected_corrections[], confidence, statistics {suspicious_tokens, candidates_evaluated, accepted_corrections, rejected_corrections, average_confidence, protected_entities, validator, languages_detected[]}, entities {type -> [{value, normalized}]} (extracted from semantic_text), processing_time_ms`.

## Forensic guarantees

`raw_text`/`cleaned_text`/`enhanced_text` are never modified; only accepted, context-validated corrections reach `semantic_text`. Every correction records the validator, its confidence and the reason (auditable). Forensic entities are placeholder-shielded before the model sees the text and restored byte-for-byte, so a URL/email/hash can never be altered. With the heuristic validator the module is fully deterministic; with XLM-R it is deterministic up to the fixed pretrained weights (no randomised decoding — fill-mask probabilities only).

## Installation (optional model)

The engine works out of the box with the offline heuristic validator. To enable XLM-R:

```bash
pip install transformers torch      # ~= the two commented lines in requirements.txt
```

`xlm-roberta-base` (~1.1 GB) downloads once on first use and is cached by Hugging Face. If Transformers or the weights are unavailable, the pipeline logs a warning and transparently uses the heuristic validator — it never crashes the investigation pipeline.

## Developer guide

New validators implement one method:

```python
class MyValidator(BaseSemanticValidator):
    name = "my-model"
    def validate(self, sentence_with_slot, original, candidate) -> ValidationVerdict:
        # sentence_with_slot contains SLOT where the token sits
        return ValidationVerdict(fits=..., confidence=...)
```

The semantic suite contains 65 collected offline tests across the engine,
knowledge base and merge integration. `FakeValidator` exercises accept/reject
logic deterministically, including entity protection, mixed-script detection,
sentence building, forensic invariants, heuristic fallback and proof that the
`semantic_correction` section is appended without changing earlier stages.

## Assumptions & limitations

- Candidate quality bounds correction quality: the LM only *ranks/validates* rule candidates, so a correction the rule layer cannot propose will not appear (by design — the model never invents text).
- XLM-R fill-mask scoring compares first-subword probabilities; multi-subword Devanagari words are validated approximately. This is a deliberate lightweight inference heuristic, not a fine-tuned classifier.
- Roman-Nepali validation relies on the pretrained model's exposure to romanised Nepali, which is limited; the confidence threshold guards against over-correction.

## Future work

Replace `XLMRobertaValidator` with a fine-tuned Nepali/Roman-Nepali validator (drop-in, no pipeline change); add pseudo-perplexity full-sentence scoring; extend the mixed-script detector to more scripts.
