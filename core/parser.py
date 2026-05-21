import re

# ─────────────────────────────────────────────────────────────────────────────
# NOISE FILTER — phrases that indicate system messages, not human speech.
# These are stripped BEFORE any structural processing.
# ─────────────────────────────────────────────────────────────────────────────
_NOISE_PHRASES = [
    "<media omitted>", "image omitted", "video omitted", "audio omitted",
    "sticker omitted", "contact card omitted", "gif omitted", "document omitted",
    "this message was deleted", "you deleted this message",
    "messages and calls are end-to-end encrypted",
    "missed voice call", "missed video call", "missed video call",
    "null"
]

# WhatsApp timestamp — STRICT anchored patterns (timestamp REQUIRED)
# iOS:     [DD/MM/YY, HH:MM:SS] Name: text
# Android: DD/MM/YY, HH:MM - Name: text
_TS_PATTERN = re.compile(
    r'^(?:'
    r'\[\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APMapm]{2})?\]\s*'   # iOS
    r'|'
    r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4},?\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[APMapm]{2})?\s*-\s*'   # Android
    r')([^:]+):\s*(.*)',
    re.UNICODE
)

# Valid human name: letters, spaces, hyphens, apostrophes, dots. 2–40 chars.
_VALID_NAME = re.compile(r"^[A-Za-z][A-Za-z\s\-'.]{1,39}$")


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _is_noise(text: str) -> bool:
    """Return True if the text is a WhatsApp system / omission notice."""
    lower = text.lower()
    return any(phrase in lower for phrase in _NOISE_PHRASES)


def _parse_raw_entries(file_content: str) -> list[dict]:
    """
    Pass 1 — Raw entry extraction.
    - Reads every line.
    - Drops noise lines immediately.
    - Parses timestamped lines into {speaker, text} entries.
    - Appends continuation lines (no timestamp) to the previous entry.
    """
    entries: list[dict] = []

    for line in file_content.splitlines():
        line = line.strip()
        if not line:
            continue

        # Drop system noise immediately
        if _is_noise(line):
            continue

        match = _TS_PATTERN.match(line)
        if match:
            speaker = match.group(1).strip()
            text = match.group(2).strip()

            # Name must look like a real human name
            if not _VALID_NAME.match(speaker):
                continue

            # Drop message bodies that are just noise phrases
            if _is_noise(text):
                continue

            if text:
                entries.append({"speaker": speaker, "text": text})
        else:
            # Continuation of previous message (multi-line text without timestamp)
            if entries and not _is_noise(line):
                entries[-1]["text"] += " " + line

    return entries


def _aggregate_turns(entries: list[dict]) -> list[dict]:
    """
    Pass 2 — Turn aggregation.
    Merges consecutive messages from the SAME speaker into one dialogue turn.
    Result: a clean, alternating-speaker turn list.

    Example:
      [Shekhar: "Hi", Shekhar: "How are you?", Shivanshu: "Fine"]
      → [Shekhar: "Hi How are you?", Shivanshu: "Fine"]
    """
    if not entries:
        return []

    turns: list[dict] = []
    current = {"speaker": entries[0]["speaker"], "text": entries[0]["text"]}

    for entry in entries[1:]:
        if entry["speaker"] == current["speaker"]:
            current["text"] += " " + entry["text"]
        else:
            turns.append(current)
            current = {"speaker": entry["speaker"], "text": entry["text"]}

    turns.append(current)
    return turns


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def parse_whatsapp_to_pairs(file_content: str, target_persona: str) -> list[dict]:
    """
    Main pipeline: Clean → Aggregate → Sliding-Window Context-Response Pairs.

    For every turn where `target_persona` is speaking, produces a training tuple:
      - immediate_context  : The immediately preceding user turn (what triggered the reply)
      - friend_response    : What the target persona said (aggregated full turn)
      - metadata_history   : The 1–2 turns before the immediate context
                             (gives the model depth / conversational memory)

    Returns a list of dicts with those three keys.
    """
    entries = _parse_raw_entries(file_content)
    turns   = _aggregate_turns(entries)

    if not turns:
        return []

    pairs: list[dict] = []

    for i, turn in enumerate(turns):
        if turn["speaker"].lower() != target_persona.lower():
            continue

        friend_response = turn["text"]

        if i == 0:
            # Target persona initiated the conversation cold
            immediate_context = "[Conversation Started]"
            metadata_history  = "System: Cold Start / Initial Conversation Initialization"
        else:
            prev = turns[i - 1]
            immediate_context = prev["text"]

            # Collect up to 2 turns before the immediate context for history window
            history_window = []
            for j in range(max(0, i - 3), i - 1):
                h = turns[j]
                history_window.append(f"{h['speaker']}: {h['text']}")

            metadata_history = (
                "\n".join(history_window)
                if history_window
                else "System: Cold Start / Initial Conversation Initialization"
            )

        pairs.append({
            "immediate_context": immediate_context,
            "friend_response":   friend_response,
            "metadata_history":  metadata_history
        })

    return pairs


def get_unique_speakers(file_content: str) -> list[str]:
    """
    Returns a sorted list of unique, valid human speaker names found in the log.
    Only considers timestamped lines — content inside message bodies is ignored.
    """
    speakers: set[str] = set()

    for line in file_content.splitlines():
        line = line.strip()
        if _is_noise(line):
            continue
        match = _TS_PATTERN.match(line)
        if match:
            candidate = match.group(1).strip()
            if _VALID_NAME.match(candidate):
                speakers.add(candidate)

    return sorted(speakers)


def parse_chat_log(file_content: str, target_persona: str = None) -> list[dict]:
    """
    Backwards-compatibility shim used by blueprints/chat.py.

    Wraps `parse_whatsapp_to_pairs` and returns dicts with keys:
      - context          : immediate_context  (what was said to the persona)
      - response         : friend_response    (what the persona replied)
      - metadata_history : sliding-window history (passed to the embedding pipeline)
    """
    if not target_persona:
        return []

    pairs = parse_whatsapp_to_pairs(file_content, target_persona)

    return [
        {
            "context":          p["immediate_context"],
            "response":         p["friend_response"],
            "metadata_history": p["metadata_history"]
        }
        for p in pairs
    ]
