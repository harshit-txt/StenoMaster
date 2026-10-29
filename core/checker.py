"""
core/checker.py  -  the transcription checker (marking engine)
================================================================

compare_texts(original, typed) lines the typed passage up against the original
passage WORD BY WORD and counts mistakes the way the stenography skill test does.

MARKING RULES USED (edit the RULES / constants below to change them)
--------------------------------------------------------------------
FULL mistake (1.0 each)
    * a word or figure that is omitted            -> "missing"
    * a word or figure that is added / repeated   -> "extra"
    * a word typed in place of another word       -> "wrong"
    * an incomplete word (e.g. "recei" for "receive")
    * a whole word typed in CAPITAL LETTERS (when the passage has it in normal case)
HALF mistake (0.5 each)
    * a spelling error                             -> "spelling"
    * singular typed for plural or the reverse     -> counted under "spelling"
    * a capital letter missing at the start of a sentence or on a proper noun
    * a full stop missing at the end of a sentence, or a full stop in a wrong place
NOT counted
    * commas, semicolons, quotes, hyphens and other punctuation
      (switch on with RULES['COUNT_OTHER_PUNCTUATION'])
    * a figure typed as digits or as words (10 / ten)
    * accepted spelling variants (see ACCEPTED_VARIANTS, e.g. Honourable / Hon'ble)
    * extra spaces, line breaks, a space before a comma, etc.

Mistake percentage = mistakes / words in the original passage * 100
(rounded to 2 decimals).  Accuracy = 100 - mistake percentage.

HOW THE WORD MATCHING WORKS (why one missing word no longer shifts everything)
------------------------------------------------------------------------------
1. Both passages are split into words (stand-alone punctuation is glued to the
   neighbouring word so it is not treated as an extra word).
2. difflib finds the longest runs of identical words and uses them as anchors.
3. In the small gaps between anchors a tiny edit-distance search pairs up the
   most similar words, so "relaesed" is matched with "released" instead of being
   reported as one missing word plus one extra word.
"""

import re
from difflib import SequenceMatcher

# --------------------------------------------------------------------------
#  EDIT HERE  -  rule switches and tunable numbers
# --------------------------------------------------------------------------
FULL = 1.0   # weight of a full mistake
HALF = 0.5   # weight of a half mistake

RULES = {
    # A typed word counts as a SPELLING error (half) instead of a WRONG word (full)
    # when it looks at least this much like the original (0.0 - 1.0).
    # Lower it to be stricter (more "wrong" words), raise it to be more lenient.
    'SPELLING_SIMILARITY': 0.75,
    # Words shorter than this can never be a "spelling" error (so "he" for "she" is wrong).
    'MIN_LEN_FOR_SPELLING': 4,
    # Capital letter missing at sentence start / proper noun  -> half mistake
    'COUNT_CAPITALISATION': True,
    # Full stop missing or in the wrong place                  -> half mistake
    'COUNT_FULL_STOP': True,
    # Commas, semicolons, quotes, hyphens ... -> half mistake. OFF in the real test.
    'COUNT_OTHER_PUNCTUATION': False,
    # A whole word typed in capitals (original is not in capitals) -> full mistake
    'COUNT_ALL_CAPS_WORD': True,
}

# Error limits shown on the result page (percent of mistakes allowed).
# EDIT: check your latest notice and change these two numbers if needed.
ERROR_LIMITS = (5.0, 10.0)

# Words that may be written in several accepted ways. Any word in a group is
# treated as identical to the others. Add your own groups (lower case, no
# surrounding punctuation).
ACCEPTED_VARIANTS = [
    {"honourable", "hon'ble", "hon", "honorable"},
    {"judgment", "judgement"},
    # {"programme", "program"},     # <- example of how to add one
]

# Figures may be typed as digits or words. Add more pairs if you need them.
NUMBER_WORDS = {
    'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5',
    'six': '6', 'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10',
    'eleven': '11', 'twelve': '12', 'thirteen': '13', 'fourteen': '14',
    'fifteen': '15', 'sixteen': '16', 'seventeen': '17', 'eighteen': '18',
    'nineteen': '19', 'twenty': '20', 'thirty': '30', 'forty': '40',
    'fifty': '50', 'sixty': '60', 'seventy': '70', 'eighty': '80',
    'ninety': '90', 'hundred': '100',
}

# The edit-distance search between anchors is skipped for gaps bigger than this
# (original words x typed words) and words are simply paired in order instead.
MAX_GAP_CELLS = 22500

# --------------------------------------------------------------------------
#  Internal helpers (you normally do not need to touch anything below)
# --------------------------------------------------------------------------
_CANON = {}
for _group in ACCEPTED_VARIANTS:
    _rep = sorted(_group)[0]
    for _w in _group:
        _CANON[_w] = _rep

# Smart quotes / dashes -> plain ones, so "don’t" and "don't" match.
_CHAR_MAP = str.maketrans({
    '‘': "'", '’': "'", '“': '"', '”': '"',
    '–': '-', '—': '-', ' ': ' ', '​': '',
})
_OPENERS = set('([{"\'')


def _normalize_chars(text):
    return (text or '').translate(_CHAR_MAP)


def _is_pure_punct(token):
    return not any(ch.isalnum() for ch in token)


def tokenize(text):
    """Split text into words. Stand-alone punctuation (" , " or " ( ") is glued
    to the neighbouring word so it never becomes an 'extra word'."""
    tokens = []
    pending = ''          # opening brackets/quotes waiting for the next word
    for tok in _normalize_chars(text).split():
        if _is_pure_punct(tok):
            if all(ch in _OPENERS for ch in tok):
                pending += tok
            elif tokens:
                tokens[-1] += tok
            else:
                pending += tok
        else:
            tokens.append(pending + tok)
            pending = ''
    if pending:
        if tokens:
            tokens[-1] += pending
        else:
            tokens.append(pending)
    return tokens


def split_word(token):
    """'(Hello,' -> ('(', 'Hello', ',')   lead punctuation, core word, trailing punctuation"""
    n = len(token)
    i = 0
    while i < n and not token[i].isalnum():
        i += 1
    j = n
    while j > i and not token[j - 1].isalnum():
        j -= 1
    return token[:i], token[i:j], token[j:]


def _key(core, token):
    """Comparison key of a word: lower case, accepted variants and figures merged."""
    if not core:
        return token
    k = core.lower()
    k = _CANON.get(k, k)
    return NUMBER_WORDS.get(k, k)


class _Word:
    __slots__ = ('tok', 'lead', 'core', 'trail', 'key')

    def __init__(self, tok):
        self.tok = tok
        self.lead, self.core, self.trail = split_word(tok)
        self.key = _key(self.core, tok)


def _sim(a, b):
    return SequenceMatcher(None, a, b).ratio()


def _align_block(o_keys, t_keys, i0, j0):
    """Pair up the words of one gap between anchors. Yields (i, j) with None for a gap."""
    a, b = len(o_keys), len(t_keys)
    if a * b > MAX_GAP_CELLS:                       # too big -> pair in order
        for k in range(max(a, b)):
            yield (i0 + k if k < a else None, j0 + k if k < b else None)
        return

    # edit distance: deleting / inserting a word costs 1, swapping a word costs
    # 1 + a small penalty for dissimilar words (so similar words get paired).
    dp = [[0.0] * (b + 1) for _ in range(a + 1)]
    for i in range(1, a + 1):
        dp[i][0] = float(i)
    for j in range(1, b + 1):
        dp[0][j] = float(j)
    sub_cost = {}
    for i in range(1, a + 1):
        for j in range(1, b + 1):
            x, y = o_keys[i - 1], t_keys[j - 1]
            if x == y:
                c = 0.0
            else:
                c = 1.0 + 0.2 * (1.0 - _sim(x, y))
            sub_cost[(i, j)] = c
            dp[i][j] = min(dp[i - 1][j - 1] + c, dp[i - 1][j] + 1.0, dp[i][j - 1] + 1.0)

    out = []
    i, j = a, b
    while i > 0 or j > 0:
        if i > 0 and j > 0 and abs(dp[i][j] - (dp[i - 1][j - 1] + sub_cost[(i, j)])) < 1e-9:
            out.append((i0 + i - 1, j0 + j - 1))
            i -= 1
            j -= 1
        elif i > 0 and abs(dp[i][j] - (dp[i - 1][j] + 1.0)) < 1e-9:
            out.append((i0 + i - 1, None))
            i -= 1
        else:
            out.append((None, j0 + j - 1))
            j -= 1
    out.reverse()
    yield from out


def _align(o_keys, t_keys):
    """Yield (i, j) index pairs: both set = matched/swapped, one None = missing/extra."""
    sm = SequenceMatcher(None, o_keys, t_keys, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                yield (i1 + k, j1 + k)
        elif tag == 'delete':
            for i in range(i1, i2):
                yield (i, None)
        elif tag == 'insert':
            for j in range(j1, j2):
                yield (None, j)
        else:  # replace
            yield from _align_block(o_keys[i1:i2], t_keys[j1:j2], i1, j1)


def _plural_variant(a, b):
    """True when the two lower-case words differ only by singular/plural ending."""
    for x, y in ((a, b), (b, a)):
        if y in (x + 's', x + 'es'):
            return True
        if x.endswith('y') and y == x[:-1] + 'ies':
            return True
    return False


def _classify_substitution(o_core, t_core):
    """A different word was typed. Is it a SPELLING slip (half) or a WRONG word (full)?"""
    a, b = o_core.lower(), t_core.lower()
    if _plural_variant(a, b):
        return 'spelling'
    if len(b) < len(a) and a.startswith(b):          # incomplete word -> full mistake
        return 'wrong'
    if (len(a) >= RULES['MIN_LEN_FOR_SPELLING'] and len(b) >= 3
            and _sim(a, b) >= RULES['SPELLING_SIMILARITY']):
        return 'spelling'
    return 'wrong'


def _all_caps_word(w):
    letters = [c for c in w.core if c.isalpha()]
    return len(letters) >= 2 and w.core.isupper()


def _extra_flags(o, t, flags):
    """Add the half-mistake flags that depend on capitals / punctuation."""
    if RULES['COUNT_CAPITALISATION'] and o.core[:1].isupper() and t.core[:1].islower():
        if 'capital' not in flags:
            flags.append('capital')
    stop_diff = ('.' in o.trail) != ('.' in t.trail)
    if RULES['COUNT_FULL_STOP'] and stop_diff:
        flags.append('punct')
    elif RULES['COUNT_OTHER_PUNCTUATION']:
        o_rest = (o.lead + o.trail).replace('.', '')
        t_rest = (t.lead + t.trail).replace('.', '')
        if o_rest != t_rest:
            flags.append('punct')


def _judge_pair(o, t, same_key):
    """Return (primary_status, [extra flags]) for one original word vs one typed word."""
    flags = []
    if (RULES['COUNT_ALL_CAPS_WORD'] and _all_caps_word(t) and not _all_caps_word(o)):
        return 'wrong', flags                         # whole word in capitals = full mistake
    if same_key:
        _extra_flags(o, t, flags)
        if not flags:
            return 'correct', flags
        return flags[0], flags[1:]
    status = _classify_substitution(o.core, t.core)
    if status == 'spelling':
        _extra_flags(o, t, flags)
    else:
        # a wrong word: only a full-stop mismatch is worth mentioning on top
        if RULES['COUNT_FULL_STOP'] and ('.' in o.trail) != ('.' in t.trail):
            flags.append('punct')
    return status, flags


def compare_texts(original, typed):
    """
    Compare the typed passage with the original and return a dict:

        diff          list of {'s': status, 'o': original word, 't': typed word, 'f': [flags]}
                      status is one of: correct, wrong, spelling, capital, punct, missing, extra
        mistakes      total mistakes (float, halves allowed)
        wrong / spelling / capital / punct / missing / extra     individual counts
        total_words   words in the original passage
        typed_words   words typed
        error_pct     mistakes / total_words * 100  (2 decimals)
        accuracy      100 - error_pct               (2 decimals)
    """
    o_words = [_Word(t) for t in tokenize(original)]
    t_words = [_Word(t) for t in tokenize(typed)]
    pairs = _align([w.key for w in o_words], [w.key for w in t_words])

    counts = {'wrong': 0, 'spelling': 0, 'capital': 0, 'punct': 0, 'missing': 0, 'extra': 0}
    diff = []
    for i, j in pairs:
        if i is not None and j is None:
            counts['missing'] += 1
            diff.append({'s': 'missing', 'o': o_words[i].tok, 't': '', 'f': []})
        elif i is None and j is not None:
            counts['extra'] += 1
            diff.append({'s': 'extra', 'o': '', 't': t_words[j].tok, 'f': []})
        else:
            o, t = o_words[i], t_words[j]
            status, flags = _judge_pair(o, t, o.key == t.key)
            if status == 'correct':
                diff.append({'s': 'correct', 'o': o.tok, 't': t.tok, 'f': []})
                continue
            counts[status] += 1
            for f in flags:
                counts[f] += 1
            diff.append({'s': status, 'o': o.tok, 't': t.tok, 'f': flags})

    mistakes = (FULL * (counts['wrong'] + counts['missing'] + counts['extra'])
                + HALF * (counts['spelling'] + counts['capital'] + counts['punct']))
    total = len(o_words)
    error_pct = round(mistakes / total * 100, 2) if total else 0.0
    accuracy = round(max(0.0, 100.0 - error_pct), 2)
    return {
        'diff': diff,
        'mistakes': mistakes,
        'wrong': counts['wrong'],
        'spelling': counts['spelling'],
        'capital': counts['capital'],
        'punct': counts['punct'],
        'missing': counts['missing'],
        'extra': counts['extra'],
        'total_words': total,
        'typed_words': len(t_words),
        'error_pct': error_pct,
        'accuracy': accuracy,
    }


def weak_word_candidates(diff):
    """Original words the student actually mistyped (wrong or spelling only).
    Missing words, extra words, capitals and full stops are NOT weak words."""
    words = []
    for item in diff:
        if item['s'] in ('wrong', 'spelling'):
            core = split_word(item['o'])[1].lower()
            if core and any(c.isalpha() for c in core):
                words.append(core)
    return words
