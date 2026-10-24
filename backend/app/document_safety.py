"""Language helpers and untrusted-document filtering for retrieval inputs."""

import re
import unicodedata
from typing import Iterable, List, Set


_INJECTION_PATTERNS = [
    r"\bignore\s+(?:all\s+)?(?:previous|prior|above|earlier|system|developer)\s+(?:instructions?|prompts?|messages?)\b",
    r"\bdisregard\s+(?:all\s+)?(?:previous|prior|above|earlier|system|developer)\s+(?:instructions?|prompts?|messages?)\b",
    r"\bforget\s+(?:all\s+)?(?:previous|prior|above|earlier|system|developer)\s+(?:instructions?|prompts?|messages?)\b",
    r"\boverride\s+(?:the\s+)?(?:system|developer|safety|security)\s+(?:instructions?|prompt|policy|rules?)\b",
    r"\bbypass\s+(?:the\s+)?(?:safety|security|policy|guardrails?)\b",
    r"\byou\s+are\s+now\s+(?:chatgpt|an?\s+assistant|a\s+different)\b",
    r"\b(?:act|roleplay|pretend)\s+as\s+(?:an?\s+)?(?:assistant|system|administrator|developer)\b",
    r"\b(?:system|developer|assistant)\s+prompt\s*[:=]",
    r"\bdo\s+not\s+(?:follow|obey|answer|tell|mention)\s+(?:the\s+)?(?:user|previous|above|system|developer)\b",
    r"\b(?:reveal|print|expose|dump|exfiltrate|send|output)\b.{0,100}\b(?:secret|api[ -]?key|password|credential|system prompt|private data)\b",
    r"\b(?:run|execute|call)\s+(?:this|the following|a)\s+(?:shell\s+)?(?:command|code|tool|script)\b",
    r"\b(?:delete|drop|truncate)\s+(?:the\s+)?(?:database|table|records?)\b",
    r"\bto=\w+\.(?:run|exec|shell|terminal)\b",
    r"<\|(?:system|assistant|developer)\|>",
    r"\bBEGIN\s+(?:SYSTEM|DEVELOPER)\s+(?:PROMPT|INSTRUCTIONS?)\b",
    r"\b(?:ignore|disregard|forget)\s+(?:all\s+)?(?:safety|security)\s+(?:rules?|checks?|policies?)\b",
    # Phase 2: broader coverage of instruction-style text planted inside documents
    r"^\s*(?:system|assistant|developer|admin|root)\s*[:>\]]",
    r"\[/?(?:INST|SYS|SYSTEM)\]",
    r"^\s*#{1,6}\s*(?:instruction|system|prompt)s?\b",
    r"\bnew\s+(?:instructions?|rules?|directives?\s+for\s+(?:the\s+)?(?:ai|assistant|model))\s*[:\-]",
    r"\b(?:note|message|instructions?|reminder)\s+(?:to|for)\s+(?:the\s+|any\s+)?(?:ai|llm|bot|model|assistant|chatbot|language\s+model|agent)\b",
    r"\b(?:ai|llm|assistant|model|agent|chatbot)s?\s+(?:reading|processing|summari[sz]ing|parsing)\s+this\b",
    r"\bwhen\s+(?:you\s+are\s+|you're\s+)?asked\s+about\b.{0,120}\b(?:respond|reply|answer|say|state|claim|report)\b",
    r"\byou\s+(?:must|should|will|shall)\s+(?:always|now|only|instead)\s+(?:say|answer|respond|reply|state|claim|report|output)\b",
    r"\b(?:reply|respond|answer)\s+only\s+with\b",
    r"\bchange\s+your\s+(?:answer|response|output|verdict)\b",
    r"\bin\s+your\s+(?:answer|response|reply|output|summary)\b.{0,80}\b(?:say|state|mark|report|claim|write|list)\b",
    r"\bdisregard\s+(?:the\s+)?(?:user|question|query|evidence|sources?)\b",
    r"\bignore\s+(?:the\s+)?(?:user|question|query|evidence|sources?|database|sql)\b",
    r"\bforget\s+everything\b",
    r"\bpretend\s+(?:you\s+are|to\s+be)\b",
    r"\b(?:jailbreak|dan\s+mode|developer\s+mode\s+enabled)\b",
    r"\boverride\s*[:=]",
    r"\bdo\s+not\s+(?:mention|cite|reveal|show|disclose|report)\b",
    r"\b(?:send|post|upload|exfiltrate|forward)\b.{0,80}\bhttps?://",
    # Hindi-language injections
    r"(?:पिछले|पहले\s*के|ऊपर\s*के|सभी)\s*(?:सभी\s*)?(?:निर्देश|आदेश)\S*\s*(?:को\s*)?(?:अनदेखा|नज़रअंदाज़|नजरअंदाज|भूल)",
    r"सिस्टम\s*प्रॉम्प्ट",
]
_INJECTION_RE = re.compile("|".join(f"(?:{pattern})" for pattern in _INJECTION_PATTERNS), re.IGNORECASE | re.MULTILINE)
_ZERO_WIDTH_RE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff\u00ad]")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?।！？])\s+")

_HI_TO_EN = {
    "स्थिति": ("status",), "हालत": ("status",), "निलंबित": ("suspended",),
    "निलंबन": ("suspension", "suspended"), "सक्रिय": ("active",), "अनुमोदित": ("approved",),
    "अस्वीकृत": ("rejected",), "कंपनी": ("company",), "संस्था": ("organization",),
    "ठेका": ("contract",), "अनुबंध": ("contract",), "दस्तावेज़": ("document",),
    "दस्तावेज": ("document",), "रिपोर्ट": ("report",), "निर्देश": ("directive",),
    "जांच": ("audit", "investigation"), "कारण": ("reason",), "क्यों": ("why",),
    "कहाँ": ("where",), "कहां": ("where",), "स्थान": ("location",), "शहर": ("city",),
    "क्षेत्र": ("region",), "मार्ग": ("path",), "रास्ता": ("path",), "संबंध": ("relationship",),
    "कनेक्शन": ("connection",), "कौन": ("who",), "क्या": ("what",), "कब": ("when",),
    "कितना": ("how", "much"), "कितनी": ("how", "much"), "कितने": ("how", "many"),
    "स्कूल": ("school",), "शिक्षा": ("education",), "स्कोर": ("score",), "औसत": ("average",),
    "ग्वालियर": ("gwalior",), "भोपाल": ("bhopal",), "जयपुर": ("jaipur",),
    "मुरैना": ("morena",), "अजमेर": ("ajmer",), "कटनी": ("katni",),
    "अडानी": ("adani",), "अदानी": ("adani",), "ग्रीन": ("green",), "एनर्जी": ("energy",),
    "लार्सन": ("larsen",), "टुब्रो": ("toubro",), "महिंद्रा": ("mahindra",),
    "रिलायंस": ("reliance",), "टाटा": ("tata",), "इंफोसिस": ("infosys",),
    "बायोकॉन": ("biocon",), "भारत": ("bharat",), "फोर्ज": ("forge",),
    "मुख्य": ("main",), "वर्तमान": ("current",), "बताएं": ("tell",), "बताइए": ("tell",),
    # Phase 2: cities, companies and relation words used in Hindi questions over English documents
    "मुंबई": ("mumbai",), "मुम्बई": ("mumbai",), "अहमदाबाद": ("ahmedabad",), "गांधीनगर": ("gandhinagar",),
    "गाँधीनगर": ("gandhinagar",), "इंडस्ट्रीज": ("industries",), "कंसल्टेंसी": ("consultancy",),
    "सर्विसेज": ("services",), "सर्विसेस": ("services",), "लिमिटेड": ("limited",),
    "आपूर्ति": ("supplies", "supply"), "सप्लाई": ("supplies", "supply"), "आपूर्तिकर्ता": ("supplier",),
    "जुड़ा": ("connected",), "जुड़ी": ("connected",), "जुड़े": ("connected",), "स्थित": ("located",),
    "प्रबंधन": ("manages",), "निदेशक": ("director",), "संयंत्र": ("plant",), "घटना": ("incident",),
    "थर्मैक्स": ("thermax",), "किर्लोस्कर": ("kirloskar",), "ब्रदर्स": ("brothers",), "सुंदरम": ("sundaram",),
    "फास्टनर्स": ("fasteners",), "हिंडाल्को": ("hindalco",), "सिप्ला": ("cipla",), "फार्मा": ("pharma",),
    "विप्रो": ("wipro",), "सिस्टम्स": ("systems",), "गोदरेज": ("godrej",), "एयरोस्पेस": ("aerospace",),
    "भेल": ("bhel",), "पावर": ("power",),
}

_HI_STOPWORDS = {
    "और", "की", "का", "के", "में", "मे", "है", "हैं", "था", "थी", "थे", "को", "से",
    "पर", "क्या", "किस", "इस", "उस", "एक", "कृपया", "बताएं", "बताइए", "मुझे", "करें",
}
_ROMAN_HI_TO_EN = {
    "sthiti": ("status",), "stithi": ("status",), "haalat": ("status",), "nilambit": ("suspended",),
    "nilamban": ("suspension",), "sakriya": ("active",), "company": ("company",), "kampani": ("company",),
    "theka": ("contract",), "anubandh": ("contract",), "dastavez": ("document",), "report": ("report",),
    "nirdesh": ("directive",), "jaanch": ("audit",), "karan": ("reason",), "kyon": ("why",),
    "kahan": ("where",), "sthan": ("location",), "shahar": ("city",), "kshetra": ("region",),
    "raasta": ("path",), "sambandh": ("relationship",), "kaun": ("who",), "kab": ("when",),
    "kitna": ("how", "much"), "kitne": ("how", "many"), "school": ("school",), "score": ("score",),
    "ausat": ("average",), "gwalior": ("gwalior",), "bhopal": ("bhopal",), "jaipur": ("jaipur",),
    "morena": ("morena",), "ajmer": ("ajmer",), "katni": ("katni",), "adani": ("adani",),
    "green": ("green",), "energy": ("energy",), "mahindra": ("mahindra",), "reliance": ("reliance",),
}
_ROMAN_HI_STOPWORDS = {"kya", "hai", "hain", "ka", "ki", "ke", "mein", "me", "ko", "se", "par", "aur", "mujhe", "batao", "bataye", "kripya"}
_ROMAN_HI_MARKERS = {
    "sthiti", "stithi", "haalat", "nilambit", "nilamban", "sakriya", "kampani", "theka", "anubandh",
    "dastavez", "nirdesh", "jaanch", "karan", "kyon", "kahan", "sthan", "shahar", "kshetra",
    "raasta", "sambandh", "kaun", "kab", "kitna", "kitne", "mujhe", "batao", "bataye", "kripya",
}
_EN_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "to", "in", "on", "for", "and",
    "or", "what", "which", "who", "when", "where", "why", "how", "please", "tell", "me",
    "show", "find", "about", "with", "from", "does", "do", "did", "has", "have", "had",
}
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[\u0900-\u097f]+|[^\W_]+", re.UNICODE)


def sanitize_document_text(text: str) -> tuple[str, int]:
    """
    Drop instruction-bearing text before indexing or graph extraction.

    Documents are treated as untrusted data, never as instructions:
    - zero-width / bidi control characters are removed so obfuscated triggers are still detected
    - hidden HTML comments are always stripped (counted when they carry an instruction)
    - a sentence containing an instruction trigger is dropped, together with the rest of its
      paragraph, because multi-sentence payloads usually follow the trigger
    Returns the safe text and the number of instruction triggers that were ignored.
    """
    normalized = _ZERO_WIDTH_RE.sub("", unicodedata.normalize("NFKC", text or ""))
    removed = 0

    def _strip_comment(match: "re.Match[str]") -> str:
        nonlocal removed
        if _INJECTION_RE.search(match.group(0)):
            removed += 1
        return " "

    normalized = _HTML_COMMENT_RE.sub(_strip_comment, normalized)
    safe: List[str] = []
    for paragraph in re.split(r"[\r\n]+", normalized):
        poisoned = False
        for piece in _SENTENCE_SPLIT_RE.split(paragraph):
            clean = piece.strip()
            if not clean:
                continue
            if _INJECTION_RE.search(clean):
                removed += 1
                poisoned = True
                continue
            if poisoned:
                # Continuation of an injected payload inside the same paragraph.
                continue
            safe.append(clean)
    return " ".join(safe), removed


def contains_instruction(text: str) -> bool:
    """True when text carries an instruction trigger (after zero-width normalization)."""
    normalized = _ZERO_WIDTH_RE.sub("", unicodedata.normalize("NFKC", text or ""))
    return bool(_INJECTION_RE.search(normalized))


def _transliterate_devanagari(word: str) -> str:
    consonants = {
        "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng", "च": "ch", "छ": "chh",
        "ज": "j", "झ": "jh", "ञ": "ny", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh",
        "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p",
        "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l",
        "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h", "क़": "q", "ख़": "kh",
        "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f",
    }
    vowels = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu", "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au"}
    signs = {"ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॅ": "e", "ॉ": "o"}
    output = ""
    for char in word:
        if char in consonants:
            output += consonants[char] + "a"
        elif char in signs:
            if output.endswith("a"):
                output = output[:-1]
            output += signs[char]
        elif char == "्":
            if output.endswith("a"):
                output = output[:-1]
        elif char in vowels:
            output += vowels[char]
        elif char in ("ं", "ँ"):
            output += "n"
        elif char == "ः":
            output += "h"
    if output.endswith("a"):
        output = output[:-1]
    return output


def expand_query_terms(query: str) -> Set[str]:
    """Return English and Hindi/transliterated terms for cross-lingual matching."""
    normalized = unicodedata.normalize("NFKC", query or "").casefold()
    tokens = _TOKEN_RE.findall(normalized)
    expanded: Set[str] = set()
    for token in tokens:
        if token in _HI_STOPWORDS or token in _ROMAN_HI_STOPWORDS or token in _EN_STOPWORDS or len(token) < 2:
            continue
        mapped = _HI_TO_EN.get(token, _ROMAN_HI_TO_EN.get(token, ()))
        expanded.update(item.casefold() for item in mapped if item.casefold() not in _EN_STOPWORDS)
        if any("\u0900" <= char <= "\u097f" for char in token):
            latin = _transliterate_devanagari(token)
            if len(latin) > 1:
                expanded.add(latin)
        else:
            expanded.add(token)
    return expanded


def normalize_multilingual_query(query: str) -> str:
    """English rendering of a (possibly Hindi) question that preserves word order,
    so multi-word names such as 'भारत फोर्ज' -> 'bharat forge' still match as phrases."""
    normalized = unicodedata.normalize("NFKC", query or "").casefold()
    ordered: List[str] = []
    for token in _TOKEN_RE.findall(normalized):
        if token in _HI_STOPWORDS or token in _ROMAN_HI_STOPWORDS or len(token) < 2:
            continue
        mapped = _HI_TO_EN.get(token, _ROMAN_HI_TO_EN.get(token, ()))
        if mapped:
            ordered.extend(item.casefold() for item in mapped)
        elif any("\u0900" <= char <= "\u097f" for char in token):
            latin = _transliterate_devanagari(token)
            if len(latin) > 1:
                ordered.append(latin)
        else:
            ordered.append(token)
    seen: Set[str] = set()
    deduped = [t for t in ordered if not (t in seen or seen.add(t))]
    return " ".join(deduped)


def is_hindi_question(query: str) -> bool:
    if any("\u0900" <= char <= "\u097f" for char in (query or "")):
        return True
    return bool(set(tokenize(query)).intersection(_ROMAN_HI_MARKERS | _ROMAN_HI_STOPWORDS))


def tokenize(text: str) -> List[str]:
    normalized = unicodedata.normalize("NFKC", text or "").casefold()
    return [token for token in _TOKEN_RE.findall(normalized) if len(token) > 1]

