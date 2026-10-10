"""Low-latency Voice AI helpers: sentence-boundary TTS chunking, VAD turn detection, and latency profiler."""
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

def chunk_text_for_streaming_tts(text: str, max_chars: int = 180) -> List[str]:
    """Split LLM response into low-latency sentence chunks for streaming TTS synthesis (sub-380ms TTFA)."""
    if not text or not text.strip():
        return []
    sentences = SENTENCE_SPLIT_RE.split(text.strip())
    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            words = sentence.split(" ")
            buf = ""
            for w in words:
                cand = f"{buf} {w}".strip() if buf else w
                if len(cand) <= max_chars:
                    buf = cand
                else:
                    if buf:
                        chunks.append(buf)
                    buf = w
            if buf:
                chunks.append(buf)
        elif not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current = f"{current} {sentence}"
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks

@dataclass
class VoiceLatencyProfiler:
    """Tracks STT, RAG retrieval, LLM TTFT, and TTS TTFA latency stages."""
    marks: Dict[str, float] = field(default_factory=dict)

    def record(self, stage: str, duration_ms: float) -> None:
        if duration_ms < 0:
            raise ValueError("duration_ms must be non-negative")
        self.marks[stage] = round(duration_ms, 2)

    @property
    def total_e2e_ms(self) -> float:
        return round(sum(self.marks.values()), 2)

    def summary(self) -> Dict[str, float]:
        return {**self.marks, "total_e2e_ms": self.total_e2e_ms}
