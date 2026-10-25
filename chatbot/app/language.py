"""Which language to answer in: the assistant mirrors the user's latest message.

English message -> English reply. Hindi + English in Roman script (Hinglish, e.g. "kal mera lecture kab hai")
-> Hinglish reply in Roman script. A message in Devanagari also gets a Roman-script Hinglish reply.

A word list is enough here: Roman Hindi uses a small set of very frequent function words (hai, kya, mera,
kab, karo, ...) that are not English words. The detected language is passed to the model with each message,
so it doesn't drift back to English (or into Devanagari) during a long conversation.
"""

from __future__ import annotations

import re

# Frequent Roman-Hindi words that are not (common) English words. Spelling variants included.
HINDI_WORDS = frozenset("""
    hai hain ho hoga hogi honge hua hui tha thi nahi nahin nhi na
    kya kyu kyun kyon kab kahan kaha kidhar kaun kon konsa kaunsa kaunse kitna kitni kitne kaise kese kaisa kaisi
    mera meri mere mujhe muje mujhko hum humein hamara hamari tum tumhara aap apna apni apne unka unki uska uski
    karo kar karna karni karde kardo krdo kro krna kijiye kariye karenge karunga karungi
    batao bata btao bataiye dikhao dikha chahiye chaiye sakta sakti sakte sakenge raha rahi rahe
    wala wali wale vala vali vale ka ki ke ko se mein mai par pe aur lekin bhi abhi kuch koi sab sabhi
    yeh ye woh wo voh jab tab agar toh phir fir ji haan han accha acha achha theek thik thek samjha samjhao
    chalo bolo dekho baare liye baad pehle pehla pehli agla agli agle pichla pichli kal aaj parso subah shaam
    raat dopahar baje bje hafte hafta mahina ghanta wahan yahan idhar udhar khali
""".split())

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_WORD = re.compile(r"[a-zA-Z]+")


def detect(text: str) -> str:
    """'hinglish' or 'english' for one user message."""
    if _DEVANAGARI.search(text):
        return "hinglish"
    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return "english"
    hits = sum(w in HINDI_WORDS for w in words)
    return "hinglish" if hits >= 2 or (hits and hits / len(words) >= 0.25) else "english"


def instruction(lang: str) -> str:
    """The reply-language line added to the message's context."""
    if lang == "hinglish":
        return ("reply language: Hinglish - the user wrote Hindi + English in Roman script, so answer the same way "
                "(Roman script only, no Devanagari; keep names, codes, rooms and times as they are)")
    return "reply language: English"
