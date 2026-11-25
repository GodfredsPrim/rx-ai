"""Prompt assembly and intake helpers without model calls or external datasets."""
import pytest
import chat_engine as chat


def test_grounded_prompt_preserves_history_and_guardrails(monkeypatch):
    monkeypatch.setattr(chat, "translate_twi_to_english", lambda text: None)
    monkeypatch.setattr(chat, "get_relevant_pdf_context", lambda messages: "PDF page 2: fixture guidance")
    history = [{"role": "user", "content": "Headache for two days"}]
    result = chat.build_system_messages(history)
    assert result[0]["role"] == "system"
    assert "Do not prescribe" in result[0]["content"]
    assert "licensed pharmacist" in result[0]["content"]
    assert "PDF page 2: fixture guidance" in result[0]["content"]
    assert result[1:] == history
    assert len(history) == 1


def test_twi_translation_and_unmatched_text(monkeypatch):
    monkeypatch.setattr(chat, "twi_dataset", [{"twi": "me ti", "en": "my head"}])
    assert chat.translate_twi_to_english(" ME TI ") == "my head"
    assert chat.translate_twi_to_english("unmatched") is None
    monkeypatch.setattr(chat, "get_relevant_pdf_context", lambda messages: "")
    result = chat.build_system_messages([{"role": "user", "content": "me ti"},
                                         {"role": "user", "content": "unmatched"}])
    assert "Answer in Twi" in result[0]["content"]
    assert result[1]["content"] == "my head"
    assert result[2]["content"] == "unmatched"


def test_image_failure_requests_description(monkeypatch):
    monkeypatch.setattr(chat, "get_relevant_pdf_context", lambda messages: "")
    def unavailable(image):
        raise RuntimeError("offline fixture")
    monkeypatch.setattr(chat, "analyze_image_with_gemini", unavailable)
    result = chat.build_system_messages([], image_data="test")
    assert "Ask the patient to describe the concern" in result[0]["content"]


@pytest.mark.parametrize("text,expected", [("chest pain", "urgent"), ("severe headache", "priority"), ("mild itch", "routine")])
def test_urgency_helper(text, expected):
    assert chat.infer_urgency_level(text) == expected


def test_symptom_metadata_and_fallback():
    assert chat.detect_symptom_metadata(["headache for two days"]) == ("head", "pain")
    summary = chat.build_fallback_consult_summary([{"role": "user", "content": "headache"}], "en")
    assert "headache" in summary
    assert "licensed pharmacist" in summary


def test_summary_format_contract():
    assert '"SUMMARY:"' in chat.SUMMARY_PROMPT
    for heading in ("CHIEF COMPLAINT", "HISTORY OF PRESENT ILLNESS", "CLINICAL RED FLAGS", "PATIENT CLINICAL CONTEXT"):
        assert heading in chat.SUMMARY_PROMPT
