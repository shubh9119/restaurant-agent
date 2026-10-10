import pytest
from voice_pipeline import chunk_text_for_streaming_tts, VoiceLatencyProfiler

def test_chunk_text_for_streaming_tts_respects_boundaries():
    text = "Hello there! Welcome to the real-time voice agent. We optimize WebRTC audio streaming for sub-380ms latency."
    chunks = chunk_text_for_streaming_tts(text, max_chars=65)
    assert len(chunks) >= 2
    assert all(len(c) <= 65 for c in chunks)
    assert " ".join(chunks) == text

def test_chunk_text_empty_input():
    assert chunk_text_for_streaming_tts("   ") == []

def test_latency_profiler_calculation():
    profiler = VoiceLatencyProfiler()
    profiler.record("stt_whisper_lora_ms", 92.4)
    profiler.record("qdrant_rag_ms", 38.1)
    profiler.record("llm_ttft_ms", 145.0)
    profiler.record("tts_ttfa_ms", 89.5)
    summary = profiler.summary()
    assert summary["total_e2e_ms"] == 365.0
