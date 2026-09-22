"""Extract verbatim CUAD clauses from formatted contract text."""

from functools import lru_cache
from itertools import islice
from statistics import fmean
from typing import Any, TypedDict

import torch
from transformers import AutoModelForQuestionAnswering, AutoTokenizer

from backend.config import MODEL_CACHE

MODEL_ID = "Rakib/roberta-base-on-cuad"
MAX_SEQUENCE_LENGTH = 512
DOCUMENT_STRIDE = 256
WINDOW_BATCH_SIZE = 4
MAX_ANSWER_LENGTH = 512
TOP_K = 5
N_BEST = 20
MIN_CLAUSE_CONFIDENCE = 0.1

# Clause-focused CUAD categories. Parties and expiration dates are produced by
# their dedicated extractors and are excluded from clause extraction.
CUAD_CATEGORIES = (
    ("Document Name", "The name of the contract"),
    ("Agreement Date", "The date of the contract"),
    ("Effective Date", "The date when the contract is effective"),
    (
        "Renewal Term",
        "What is the renewal term after the initial term expires? This includes "
        "automatic extensions and unilateral extensions with prior notice.",
    ),
    (
        "Notice Period to Terminate Renewal",
        "What is the notice period required to terminate renewal?",
    ),
    (
        "Governing Law",
        "Which state/country's law governs the interpretation of the contract?",
    ),
    (
        "Most Favored Nation",
        "Is there a clause that if a third party gets better terms on the licensing "
        "or sale of technology/goods/services described in the contract, the buyer "
        "of such technology/goods/services under the contract shall be entitled to "
        "those better terms?",
    ),
    (
        "Non-Compete",
        "Is there a restriction on the ability of a party to compete with the "
        "counterparty or operate in a certain geography or business or technology "
        "sector?",
    ),
    (
        "Exclusivity",
        "Is there an exclusive dealing commitment with the counterparty? This "
        "includes a commitment to procure all requirements from one party of "
        "certain technology, goods, or services or a prohibition on licensing or "
        "selling technology, goods or services to third parties, or a prohibition "
        "on collaborating or working with other parties, whether during the "
        "contract or after the contract ends (or both).",
    ),
    (
        "No-Solicit of Customers",
        "Is a party restricted from contracting or soliciting customers or "
        "partners of the counterparty, whether during the contract or after the "
        "contract ends (or both)?",
    ),
    (
        "Competitive Restriction Exception",
        "This category includes the exceptions or carveouts to Non-Compete, "
        "Exclusivity and No-Solicit of Customers above.",
    ),
    (
        "No-Solicit of Employees",
        "Is there a restriction on a party's soliciting or hiring employees and/or "
        "contractors from the counterparty, whether during the contract or after "
        "the contract ends (or both)?",
    ),
    (
        "Non-Disparagement",
        "Is there a requirement on a party not to disparage the counterparty?",
    ),
    (
        "Termination for Convenience",
        "Can a party terminate this contract without cause (solely by giving a "
        "notice and allowing a waiting period to expire)?",
    ),
    (
        "Rofr/Rofo/Rofn",
        "Is there a clause granting one party a right of first refusal, right of "
        "first offer or right of first negotiation to purchase, license, market, "
        "or distribute equity interest, technology, assets, products or services?",
    ),
    (
        "Change of Control",
        "Does one party have the right to terminate or is consent or notice "
        "required of the counterparty if such party undergoes a change of control, "
        "such as a merger, stock sale, transfer of all or substantially all of its "
        "assets or business, or assignment by operation of law?",
    ),
    (
        "Anti-Assignment",
        "Is consent or notice required of a party if the contract is assigned to a "
        "third party?",
    ),
    (
        "Revenue/Profit Sharing",
        "Is one party required to share revenue or profit with the counterparty for "
        "any technology, goods, or services?",
    ),
    (
        "Price Restrictions",
        "Is there a restriction on the ability of a party to raise or reduce prices "
        "of technology, goods, or services provided?",
    ),
    (
        "Minimum Commitment",
        "Is there a minimum order size or minimum amount or units per-time period "
        "that one party must buy from the counterparty under the contract?",
    ),
    (
        "Volume Restriction",
        "Is there a fee increase or consent requirement, etc. if one party's use of "
        "the product/services exceeds certain threshold?",
    ),
    (
        "IP Ownership Assignment",
        "Does intellectual property created by one party become the property of the "
        "counterparty, either per the terms of the contract or upon the occurrence "
        "of certain events?",
    ),
    (
        "Joint IP Ownership",
        "Is there any clause providing for joint or shared ownership of intellectual "
        "property between the parties to the contract?",
    ),
    (
        "License Grant",
        "Does the contract contain a license granted by one party to its counterparty?",
    ),
    (
        "Non-Transferable License",
        "Does the contract limit the ability of a party to transfer the license "
        "being granted to a third party?",
    ),
    (
        "Affiliate License-Licensor",
        "Does the contract contain a license grant by affiliates of the licensor or "
        "that includes intellectual property of affiliates of the licensor?",
    ),
    (
        "Affiliate License-Licensee",
        "Does the contract contain a license grant to a licensee (including a "
        "sublicensor) and the affiliates of such licensee/sublicensor?",
    ),
    (
        "Unlimited/All-You-Can-Eat-License",
        "Is there a clause granting one party an enterprise, all you can eat or "
        "unlimited usage license?",
    ),
    (
        "Irrevocable or Perpetual License",
        "Does the contract contain a license grant that is irrevocable or perpetual?",
    ),
    (
        "Source Code Escrow",
        "Is one party required to deposit its source code into escrow with a third "
        "party, which can be released to the counterparty upon the occurrence of "
        "certain events (bankruptcy, insolvency, etc.)?",
    ),
    (
        "Post-Termination Services",
        "Is a party subject to obligations after the termination or expiration of a "
        "contract, including any post-termination transition, payment, transfer of "
        "IP, wind-down, last-buy, or similar commitments?",
    ),
    (
        "Audit Rights",
        "Does a party have the right to audit the books, records, or physical "
        "locations of the counterparty to ensure compliance with the contract?",
    ),
    (
        "Uncapped Liability",
        "Is a party's liability uncapped upon the breach of its obligation in the "
        "contract? This also includes uncapped liability for a particular type of "
        "breach such as IP infringement or breach of confidentiality obligation.",
    ),
    (
        "Cap on Liability",
        "Does the contract include a cap on liability upon the breach of a party's "
        "obligation? This includes time limitation for the counterparty to bring "
        "claims or maximum amount for recovery.",
    ),
    (
        "Liquidated Damages",
        "Does the contract contain a clause that would award either party liquidated "
        "damages for breach or a fee upon the termination of a contract "
        "(termination fee)?",
    ),
    (
        "Warranty Duration",
        "What is the duration of any warranty against defects or errors in "
        "technology, products, or services provided under the contract?",
    ),
    (
        "Insurance",
        "Is there a requirement for insurance that must be maintained by one party "
        "for the benefit of the counterparty?",
    ),
    (
        "Covenant Not to Sue",
        "Is a party restricted from contesting the validity of the counterparty's "
        "ownership of intellectual property or otherwise bringing a claim against "
        "the counterparty for matters unrelated to the contract?",
    ),
    (
        "Third Party Beneficiary",
        "Is there a non-contracting party who is a beneficiary to some or all of the "
        "clauses in the contract and therefore can enforce its rights against a "
        "contracting party?",
    ),
)


class FormattedText(TypedDict):
    """Input produced by ``text_formatter.format_text``."""

    text: str
    confidence: float
    source: str


class Clause(TypedDict):
    """A verbatim clause and its CUAD category."""

    category: str
    text: str
    confidence: float


class ClauseResult(TypedDict):
    """Extracted clauses and document-level confidence."""

    clauses: list[Clause]
    confidence: float
    source: str


class _Candidate(TypedDict):
    category: str
    text: str
    start: int
    end: int
    score: float


class _Answer(TypedDict):
    answer: str
    score: float
    start: int
    end: int


@lru_cache(maxsize=1)
def _get_clause_components() -> tuple[Any, Any]:
    """Download the CUAD model if needed and initialize local inference once."""

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, cache_dir=MODEL_CACHE)
    model = AutoModelForQuestionAnswering.from_pretrained(
        MODEL_ID,
        cache_dir=MODEL_CACHE,
    )
    model.eval()
    return tokenizer, model


def _question_windows(tokenizer: Any, question: str, context: str):
    """Build RoBERTa question/context windows with original character offsets."""

    question_ids = tokenizer(
        question, add_special_tokens=False, truncation=False, padding=False,
        verbose=False,
    )["input_ids"]
    document = tokenizer(
        context, add_special_tokens=False, truncation=False, padding=False,
        return_offsets_mapping=True, verbose=False,
    )
    # RoBERTa pairs use <s> question </s></s> context </s>.
    prefix = [tokenizer.cls_token_id, *question_ids,
              tokenizer.sep_token_id, tokenizer.sep_token_id]
    capacity = MAX_SEQUENCE_LENGTH - len(prefix) - 1
    if capacity <= 0:
        raise ValueError("CUAD question leaves no room for contract tokens")
    overlap = min(DOCUMENT_STRIDE, capacity - 1)
    ids = document["input_ids"]
    offsets = document["offset_mapping"]
    for start in range(0, len(ids), capacity - overlap):
        end = min(start + capacity, len(ids))
        yield (
            prefix + ids[start:end] + [tokenizer.sep_token_id],
            [None] * len(prefix) + [1] * (end - start) + [None],
            [(0, 0)] * len(prefix) + list(offsets[start:end]) + [(0, 0)],
        )
        if end == len(ids):
            break


def _window_predictions(tokenizer: Any, model: Any, question: str, context: str):
    """Run bounded batches, leaving offsets anchored to the complete contract."""

    windows = iter(_question_windows(tokenizer, question, context))
    while batch := list(islice(windows, WINDOW_BATCH_SIZE)):
        width = max(len(ids) for ids, _, _ in batch)
        input_ids = torch.tensor([
            ids + [tokenizer.pad_token_id] * (width - len(ids))
            for ids, _, _ in batch
        ])
        attention_mask = torch.tensor([
            [1] * len(ids) + [0] * (width - len(ids))
            for ids, _, _ in batch
        ])
        with torch.inference_mode():
            output = model(input_ids=input_ids, attention_mask=attention_mask)
        for index, (ids, sequence_ids, offsets) in enumerate(batch):
            yield (sequence_ids, offsets, output.start_logits[index, :len(ids)],
                   output.end_logits[index, :len(ids)])


def _answer_question(question: str, context: str) -> list[_Answer]:
    """Run extractive QA over explicit windows of the complete context."""

    tokenizer, model = _get_clause_components()

    candidates: dict[tuple[int, int], _Answer] = {}
    null_scores: list[float] = []

    for sequence_ids, offsets, start_logits, end_logits in _window_predictions(
        tokenizer, model, question, context
    ):
        cls_index = 0

        valid_mask = torch.tensor(
            [sequence_id == 1 for sequence_id in sequence_ids],
            dtype=torch.bool,
            device=start_logits.device,
        )
        valid_mask[cls_index] = True

        start_logits = start_logits.masked_fill(
            ~valid_mask, float("-inf")
        )
        end_logits = end_logits.masked_fill(
            ~valid_mask, float("-inf")
        )
        start_probabilities = torch.softmax(start_logits, dim=0)
        end_probabilities = torch.softmax(end_logits, dim=0)
        null_scores.append(
            float(start_probabilities[cls_index] * end_probabilities[cls_index])
        )

        start_indexes = torch.topk(
            start_probabilities, min(N_BEST, start_probabilities.shape[0])
        ).indices.tolist()
        end_indexes = torch.topk(
            end_probabilities, min(N_BEST, end_probabilities.shape[0])
        ).indices.tolist()

        for start_index in start_indexes:
            if sequence_ids[start_index] != 1:
                continue
            for end_index in end_indexes:
                if sequence_ids[end_index] != 1 or end_index < start_index:
                    continue
                if end_index - start_index + 1 > MAX_ANSWER_LENGTH:
                    continue

                start = int(offsets[start_index][0])
                end = int(offsets[end_index][1])
                if end <= start:
                    continue

                score = float(
                    start_probabilities[start_index] * end_probabilities[end_index]
                )
                answer = {
                    "answer": context[start:end],
                    "score": score,
                    "start": start,
                    "end": end,
                }
                existing = candidates.get((start, end))
                if existing is None or score > existing["score"]:
                    candidates[(start, end)] = answer

    ranked = sorted(
        candidates.values(),
        key=lambda answer: answer["score"],
        reverse=True,
    )
    ranked = ranked[:TOP_K]
    ranked.append(
        {
            "answer": "",
            "score": min(null_scores, default=0.0),
            "start": 0,
            "end": 0,
        }
    )
    return ranked


def _question(category: str, description: str) -> str:
    return (
        "Highlight the parts (if any) of this contract related to "
        f'"{category}" that should be reviewed by a lawyer. Details: {description}'
    )


def _overlap_ratio(left: _Candidate, right: _Candidate) -> float:
    intersection = max(
        0,
        min(left["end"], right["end"]) - max(left["start"], right["start"]),
    )
    shorter_length = min(left["end"] - left["start"], right["end"] - right["start"])
    return intersection / shorter_length if shorter_length else 0.0


def _deduplicate(candidates: list[_Candidate]) -> list[_Candidate]:
    """Keep the strongest of substantially overlapping answers per category."""

    kept: list[_Candidate] = []
    for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True):
        duplicate = any(
            candidate["category"] == existing["category"]
            and _overlap_ratio(candidate, existing) >= 0.8
            for existing in kept
        )
        if not duplicate:
            kept.append(candidate)

    return sorted(kept, key=lambda item: (item["start"], item["end"], item["category"]))


def extract_clauses(formatted_text: FormattedText) -> ClauseResult:
    """Extract CUAD clause spans directly from formatted contract text.

    Explicit overlapping windows fit each question and context into 512 tokens.
    Answers are reconstructed with character offsets into the original text so
    the returned clause text is never generated, normalized, or rewritten.
    """

    text = formatted_text["text"]
    if not text.strip():
        return {
            "clauses": [],
            "confidence": 0.0,
            "source": formatted_text["source"],
        }

    candidates: list[_Candidate] = []

    for category, description in CUAD_CATEGORIES:
        answers = _answer_question(_question(category, description), text)
        null_score = max(
            (
                float(answer["score"])
                for answer in answers
                if not str(answer.get("answer", "")).strip()
            ),
            default=0.0,
        )

        for answer in answers:
            score = float(answer["score"])
            if not str(answer.get("answer", "")).strip():
                continue
            if score < MIN_CLAUSE_CONFIDENCE or score <= null_score:
                continue

            start = int(answer["start"])
            end = int(answer["end"])
            if start < 0 or end <= start or end > len(text):
                continue

            candidates.append(
                {
                    "category": category,
                    "text": text[start:end],
                    "start": start,
                    "end": end,
                    "score": score,
                }
            )

    clauses_with_scores = _deduplicate(candidates)
    clauses: list[Clause] = [
        {
            "category": candidate["category"],
            "text": candidate["text"],
            "confidence": float(formatted_text["confidence"] * candidate["score"]),
        }
        for candidate in clauses_with_scores
    ]
    overall_confidence = (
        fmean(clause["confidence"] for clause in clauses) if clauses else 0.0
    )

    return {
        "clauses": clauses,
        "confidence": float(overall_confidence),
        "source": formatted_text["source"],
    }
