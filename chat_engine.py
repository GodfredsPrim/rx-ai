"""
chat_engine.py – Shared clinical‑chat logic used by both the web API
(/api/chat) and the WhatsApp bot.

Everything LLM‑ / dataset‑ / triage‑related lives here so there is a
single source of truth.
"""

from pathlib import Path
from typing import List
import csv
import os
import re

import pypdf
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy.orm import Session

import models

# ── env / paths ──────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True, verbose=True)

# ── LLM client ──────────────────────────────────────────────────────
api_key = os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", "dummy_key"))
configured_base_url = os.getenv("DEEPSEEK_BASE_URL", "").strip()
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

if configured_base_url:
    base_url = configured_base_url
elif api_key.startswith("sk-"):
    base_url = "https://api.openai.com/v1"
else:
    base_url = "https://api.deepseek.com"

openai_client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    timeout=LLM_TIMEOUT_SECONDS,
    max_retries=LLM_MAX_RETRIES,
)

_default_model = (
    "gpt-4o-mini"
    if api_key.startswith("sk-") and not configured_base_url
    else "deepseek-chat"
)
MODEL_NAME = os.getenv("MODEL_NAME", _default_model)


# ── text helpers ─────────────────────────────────────────────────────
def clean_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def chunk_text(text: str, chunk_size: int = 180, overlap: int = 40) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break
    return chunks


def tokenize(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


# ── PDF loader ───────────────────────────────────────────────────────
def _find_guidelines_pdf() -> Path | None:
    configured = os.getenv("GUIDELINES_PDF_PATH")
    if configured:
        pdf_path = Path(configured)
        if pdf_path.exists():
            return pdf_path
    pdf_files = sorted(BASE_DIR.glob("*.pdf"))
    return pdf_files[0] if pdf_files else None


def load_pdf_chunks() -> tuple[str, list[dict]]:
    pdf_path = _find_guidelines_pdf()
    if not pdf_path:
        return "", []
    full_text_parts: list[str] = []
    chunks: list[dict] = []
    try:
        reader = pypdf.PdfReader(str(pdf_path))
        for page_index, page in enumerate(reader.pages, start=1):
            page_text = clean_whitespace(page.extract_text() or "")
            if not page_text:
                continue
            full_text_parts.append(page_text)
            for c in chunk_text(page_text):
                chunks.append({"page": page_index, "text": c, "tokens": tokenize(c)})
    except Exception as exc:
        print(f"Failed to load PDF context: {exc}")
        return "", []
    return "\n".join(full_text_parts), chunks


# ── dataset loaders ──────────────────────────────────────────────────
def load_medicine_dataset() -> List[dict]:
    csv_path = BASE_DIR / "medicine_dataset.csv"
    if not csv_path.exists():
        return []
    medicines: list[dict] = []
    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["_tokens"] = tokenize(
                    row.get("Name", "") + " " + row.get("Category", "")
                )
                medicines.append(row)
    except Exception as exc:
        print(f"Failed to load medicine dataset: {exc}")
    return medicines


def load_twi_dataset() -> List[dict]:
    csv_path = BASE_DIR / "Public - Twi[Twi-En]_70.csv"
    if not csv_path.exists():
        csv_path = BASE_DIR / "Public%20-%20Twi%5BTwi-En%5D_70.csv"
    if not csv_path.exists():
        return []
    twi_entries: list[dict] = []
    try:
        with open(csv_path, mode="r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                twi_text = (row.get("text") or "").strip()
                en_text = (row.get("label") or row.get("Comments") or "").strip()
                if twi_text and en_text:
                    twi_entries.append({"twi": twi_text, "en": en_text})
    except Exception as exc:
        print(f"Failed to load Twi dataset: {exc}")
    return twi_entries


def load_final_dataset() -> List[dict]:
    csv_path = BASE_DIR / "final.csv"
    if not csv_path.exists():
        return []
    entries: list[dict] = []
    try:
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                disease = row.get("disease", "").strip()
                drug = row.get("drug", "").strip()
                if disease and drug:
                    entries.append(
                        {
                            "disease": disease,
                            "drug": drug,
                            "_tokens": tokenize(disease + " " + drug),
                        }
                    )
    except Exception as exc:
        print(f"Failed to load final dataset: {exc}")
    return entries


# ── singletons ───────────────────────────────────────────────────────
pdf_context, pdf_chunks = load_pdf_chunks()
medicine_dataset = load_medicine_dataset()
twi_dataset = load_twi_dataset()
final_dataset = load_final_dataset()


# ── Twi translation ─────────────────────────────────────────────────
def translate_twi_to_english(text: str) -> str | None:
    normalized = text.strip().lower()
    for pair in twi_dataset:
        if pair["twi"].strip().lower() == normalized:
            return pair["en"]
    return None


# ── system prompt ────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are RxAI, a warm and capable clinical conversation assistant for pharmacy triage.

STYLE:
- Sound natural, calm, and caring.
- Use short, smooth replies, usually 2 to 4 sentences.
- Refer to what the user just said so the conversation feels continuous.
- Do not repeat the same empathy phrase every turn.
- Avoid sounding robotic, dramatic, or overly scripted.

CONVERSATION RULES:
1. Ask only one follow-up question per reply.
2. Wait for the user's answer before moving to the next question.
3. Start with a brief human acknowledgment, then continue naturally.
4. Gather this information before transitioning: duration, severity or progression, and other associated symptoms.
5. After enough information has been gathered, begin the reply with the exact marker [CONSULT_READY], then give a short summary and explain that the case will be sent to a licensed pharmacist for diagnosis and treatment decisions.
6. Do not prescribe and do not recommend specific drug names to the patient. The pharmacist makes the treatment decision.
7. Respond in the same language the user writes in.
8. If there are danger signs such as difficulty breathing, confusion, convulsions, jaundice, severe dehydration, or chest pain, clearly advise urgent hospital care.
9. Never dump a long checklist unless the user asks. Keep the exchange conversational.

BASE MEDICAL GUIDELINES CONTEXT:
{pdf_context[:4000]}"""

SUMMARY_PROMPT = """You are a senior clinical pharmacist specializing in emergency triage and primary care. 
Your task is to generate a HIGHLY DETAILED, PROFESSIONAL, and CLINICALLY RIGOROUS intake report from a patient conversation.

STRUCTURE YOUR REPORT AS FOLLOWS:

1. CHIEF COMPLAINT
   - Clear statement of the primary reason for the consultation.

2. HISTORY OF PRESENT ILLNESS (HPI)
   - Detailed chronological timeline of symptoms.
   - Character of symptoms (stabbing, dull, burning, etc.).
   - Exact location and radiation of symptoms.
   - Severity (on a scale or descriptive).
   - Aggravating and relieving factors.
   - Impact on daily activities.

3. ASSOCIATED SYMPTOMS & RELEVANT NEGATIVES
   - Comprehensive list of secondary symptoms mentioned.
   - Explicitly list relevant symptoms that the patient DENIES (e.g., "Patient denies fever or vomiting").

4. CLINICAL RED FLAGS & URGENCY ASSESSMENT
   - Explicitly state any life-threatening indicators (e.g., dyspnea, altered mental status, severe dehydration).
   - If no red flags are present, state "No clinical red flags identified at this time."
   - Provide a brief rationale for the assigned urgency level.

5. PATIENT CLINICAL CONTEXT
   - Summarize any mentioned chronic conditions, allergies, or current medications.

6. CLINICAL IMPRESSION / PHARMACIST GUIDANCE
   - Your professional summary of the likely clinical situation.
   - Specific areas the reviewing pharmacist should focus on during the live assessment.

Use formal clinical language (e.g., "presents with", "sequelae", "exacerbated by", "ambulatory"). 
Be extremely thorough. Use Markdown formatting with bold headers and bullet points for maximum scanability.
"""


# ── context / search helpers ────────────────────────────────────────
def get_relevant_medicine_context(messages: list[dict], limit: int = 5) -> str:
    if not medicine_dataset:
        return ""
    query_text = " ".join(
        message["content"] for message in messages if message.get("role") == "user"
    )
    query_tokens = tokenize(query_text)
    if not query_tokens:
        return ""
    scored = []
    for med in medicine_dataset:
        overlap = query_tokens.intersection(med["_tokens"])
        if overlap:
            scored.append((len(overlap), med))
    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[:limit]
    if not top:
        return ""
    context_parts: list[str] = []
    for _, med in top:
        parts = [f"Drug: {med.get('Name')}"]
        if med.get("Category"):
            parts.append(f"Category: {med.get('Category')}")
        if med.get("Indication"):
            parts.append(f"Indication: {med.get('Indication')}")
        if med.get("Dosage Form"):
            parts.append(f"Form: {med.get('Dosage Form')}")
        if med.get("Strength"):
            parts.append(f"Strength: {med.get('Strength')}")
        context_parts.append(" | ".join(parts))
    return "\n".join(context_parts)


def get_relevant_pdf_context(messages: list[dict], limit: int = 3) -> str:
    if not pdf_chunks:
        return ""
    query_text = " ".join(
        message["content"] for message in messages if message.get("role") == "user"
    )
    query_tokens = tokenize(query_text)
    if not query_tokens:
        return ""
    scored_chunks = []
    for chunk in pdf_chunks:
        overlap = query_tokens.intersection(chunk["tokens"])
        if overlap:
            scored_chunks.append((len(overlap), chunk["page"], chunk["text"]))
    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    top_chunks = scored_chunks[:limit]
    if not top_chunks:
        return ""
    return "\n\n".join(f"PDF page {page}: {text}" for _, page, text in top_chunks)


# ── symptom‑to‑drug search ──────────────────────────────────────────
_SYMPTOM_INFO = {
    "headache": {"indications": ["pain", "headache"], "dosage_hint": "Take 500mg-1g every 4-6 hours as needed, max 4g daily"},
    "fever": {"indications": ["fever", "pain"], "dosage_hint": "Take 500mg-1g every 4-6 hours as needed for fever"},
    "malaria": {"indications": ["fever", "infection", "malaria"], "dosage_hint": "Standard course: 1 tablet twice daily for 3 days with food"},
    "cough": {"indications": ["infection", "cough"], "dosage_hint": "Take 5-10ml every 4-6 hours as needed"},
    "cold": {"indications": ["infection", "virus", "cold"], "dosage_hint": "Take as directed, usually 1 tablet every 6-8 hours"},
    "flu": {"indications": ["virus", "infection", "flu"], "dosage_hint": "Take 1 tablet every 6-8 hours with food"},
    "diarrhea": {"indications": ["infection", "diarrhea"], "dosage_hint": "Take 2 tablets after each loose stool, max 8 tablets daily"},
    "stomach": {"indications": ["pain", "stomach"], "dosage_hint": "Take 1 tablet 30 minutes before meals"},
    "nausea": {"indications": ["nausea", "stomach"], "dosage_hint": "Take 25mg every 6-8 hours as needed"},
    "vomiting": {"indications": ["nausea", "vomiting"], "dosage_hint": "Take as directed, usually 10mg every 8 hours"},
    "wound": {"indications": ["wound", "infection"], "dosage_hint": "Apply topically 2-3 times daily or as directed"},
    "cut": {"indications": ["wound", "cut"], "dosage_hint": "Clean wound and apply 2-3 times daily"},
    "infection": {"indications": ["infection", "bacterial"], "dosage_hint": "Take 500mg every 6 hours or as prescribed"},
    "pain": {"indications": ["pain", "inflammation"], "dosage_hint": "Take 400-800mg every 6-8 hours as needed"},
    "inflammation": {"indications": ["pain", "inflammation"], "dosage_hint": "Take 200-400mg every 4-6 hours as needed"},
    "allergy": {"indications": ["allergy", "allergic"], "dosage_hint": "Take 10mg once daily for allergy relief"},
    "allergic": {"indications": ["allergy", "allergic"], "dosage_hint": "Take 10mg once daily"},
    "diabetes": {"indications": ["diabetes", "blood sugar"], "dosage_hint": "Take 500mg-1g twice daily with meals as prescribed"},
    "sugar": {"indications": ["diabetes", "blood sugar"], "dosage_hint": "Take as prescribed by your doctor"},
    "blood pressure": {"indications": ["hypertension", "blood pressure"], "dosage_hint": "Take 5-10mg once daily as prescribed"},
    "hypertension": {"indications": ["hypertension", "blood pressure"], "dosage_hint": "Take 5-10mg once daily"},
    "depression": {"indications": ["depression", "mental health"], "dosage_hint": "Take 20-50mg once daily as prescribed by doctor"},
    "anxiety": {"indications": ["anxiety", "mental health"], "dosage_hint": "Take as prescribed by your doctor"},
    "fungus": {"indications": ["fungus", "fungal"], "dosage_hint": "Apply to affected area once or twice daily"},
    "fungal": {"indications": ["fungus", "fungal"], "dosage_hint": "Apply to affected area once or twice daily"},
    "rash": {"indications": ["rash", "skin", "allergy"], "dosage_hint": "Apply thin layer to affected area 2-3 times daily"},
    "skin": {"indications": ["skin", "wound"], "dosage_hint": "Apply as directed to affected area"},
    "virus": {"indications": ["virus", "viral"], "dosage_hint": "Take as directed, complete full course"},
    "viral": {"indications": ["virus", "viral"], "dosage_hint": "Take as directed, rest and fluids important"},
    "sore throat": {"indications": ["infection", "sore throat"], "dosage_hint": "Dissolve 1 lozenge every 2-3 hours as needed"},
    "throat": {"indications": ["infection", "sore throat"], "dosage_hint": "Dissolve 1 lozenge every 2-3 hours"},
    "back pain": {"indications": ["pain", "back pain"], "dosage_hint": "Apply to affected area 3-4 times daily or take oral dose as needed"},
    "muscle": {"indications": ["pain", "muscle"], "dosage_hint": "Apply to affected muscles 3-4 times daily"},
}


def search_medicine_dataset(symptom_summary: str, limit: int = 5) -> list[dict]:
    if not medicine_dataset:
        return []
    query_tokens = tokenize(symptom_summary)
    if not query_tokens:
        return []

    target_indications: set[str] = set()
    matched_symptoms: set[str] = set()
    for word in query_tokens:
        if word in _SYMPTOM_INFO:
            matched_symptoms.add(word)
            for ind in _SYMPTOM_INFO[word]["indications"]:
                target_indications.add(ind.lower())

    scored: list[tuple[int, dict]] = []
    for med in medicine_dataset:
        score = 0
        med_indication = (med.get("Indication") or "").lower()
        med_category = (med.get("Category") or "").lower()
        med_name = (med.get("Name") or "").lower()
        for symptom in matched_symptoms:
            if symptom in med_indication or symptom in med_category:
                score += 5
            for ind in _SYMPTOM_INFO[symptom]["indications"]:
                if ind in med_indication:
                    score += 3
        overlap = query_tokens.intersection(med["_tokens"])
        score += len(overlap)
        common_meds = ["paracetamol", "acetaminophen", "ibuprofen", "aspirin", "ORS", "vitamin", "zinc", "amoxicillin", "coartem"]
        for common in common_meds:
            if common in med_name:
                score += 1
        if score > 0:
            scored.append((score, med))

    for entry in final_dataset:
        score = 0
        disease = entry["disease"].lower()
        drug_name = entry["drug"].lower()
        for symptom in matched_symptoms:
            if symptom in disease:
                score += 10
        overlap = query_tokens.intersection(entry["_tokens"])
        score += len(overlap)
        if score > 5:
            med_info = next(
                (m for m in medicine_dataset if m.get("Name", "").lower() == drug_name),
                None,
            )
            scored.append(
                (
                    score,
                    {
                        "Name": drug_name.title(),
                        "Category": med_info.get("Category", "Treatment") if med_info else "General medication",
                        "Dosage Form": med_info.get("Dosage Form", "Tablet/Syrup") if med_info else "As directed",
                        "Strength": med_info.get("Strength", "Standard") if med_info else "N/A",
                        "Indication": disease.title(),
                        "Classification": med_info.get("Classification", "OTC") if med_info else "General",
                        "_tokens": entry["_tokens"],
                    },
                )
            )

    scored.sort(key=lambda item: item[0], reverse=True)
    seen_names: set[str] = set()
    results: list[dict] = []
    for _, med in scored:
        name = med.get("Name", "")
        if name not in seen_names:
            seen_names.add(name)
            dosage_hint = "Take as directed by your pharmacist or doctor"
            for symptom in matched_symptoms:
                if symptom in _SYMPTOM_INFO:
                    dosage_hint = _SYMPTOM_INFO[symptom]["dosage_hint"]
                    break
            results.append(
                {
                    "name": name,
                    "category": med.get("Category", ""),
                    "dosage_form": med.get("Dosage Form", ""),
                    "strength": med.get("Strength", ""),
                    "indication": med.get("Indication", ""),
                    "classification": med.get("Classification", ""),
                    "dosage_instructions": dosage_hint,
                }
            )
        if len(results) >= max(limit, 4):
            break
    return results


def generate_detailed_summary(translated_messages: list[dict]) -> str:
    """Uses the LLM to generate a professional clinical summary from English-translated messages."""
    try:
        # We only need the user/assistant interaction history
        history_text = "\n".join(
            [f"{m['role'].upper()}: {m['content']}" for m in translated_messages if m['role'] in ['user', 'assistant']]
        )
        
        response = openai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": f"Please summarize this triage conversation with maximum clinical depth:\n\n{history_text}"}
            ],
            max_tokens=1500,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Failed to generate detailed summary: {e}")
        # Improved fallback: Filter out unhelpful short responses like "no", "yes"
        user_msgs = [
            m['content'].strip() 
            for m in translated_messages 
            if m['role'] == 'user' and len(m['content'].strip()) > 3 and m['content'].strip().lower() not in {"no", "yes", "okay", "none"}
        ]
        if not user_msgs:
            # If all are short, take the last one anyway but label it
            user_msgs = [m['content'] for m in translated_messages if m['role'] == 'user'][-2:]
        
        return "Symptom history (Auto-concatenated): " + " | ".join(user_msgs)


def search_final_dataset(symptom_summary: str, limit: int = 5) -> list[dict]:
    if not final_dataset:
        return []
    query_tokens = tokenize(symptom_summary)
    if not query_tokens:
        return []
    scored: list[tuple[int, dict]] = []
    for entry in final_dataset:
        disease = entry.get("disease", "")
        drug = entry.get("drug", "")
        disease_lower = disease.lower()
        drug_lower = drug.lower()
        overlap = len(query_tokens.intersection(entry.get("_tokens", set())))
        score = overlap
        for token in query_tokens:
            if len(token) > 2 and token in disease_lower:
                score += 4
            if len(token) > 2 and token in drug_lower:
                score += 2
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda item: item[0], reverse=True)
    seen: set[tuple[str, str]] = set()
    results: list[dict] = []
    for _, entry in scored:
        key = (entry.get("disease", "").lower(), entry.get("drug", "").lower())
        if key in seen:
            continue
        seen.add(key)
        results.append({"disease": entry.get("disease", ""), "drug": entry.get("drug", "")})
        if len(results) >= limit:
            break
    return results


# ── conversation analysis ────────────────────────────────────────────
def analyze_conversation_state(translated_messages: list[dict]) -> dict:
    user_messages = [
        message["content"].strip()
        for message in translated_messages
        if message.get("role") == "user" and message.get("content", "").strip()
    ]
    latest_message = user_messages[-1] if user_messages else ""
    combined_text = " ".join(user_messages).lower()

    has_duration = bool(
        re.search(
            r"\b(\d+\s*(hour|hours|day|days|week|weeks|month|months)|today|yesterday|since|for\s+\d+|this morning|last night)\b",
            combined_text,
        )
    )
    has_severity = bool(
        re.search(
            r"\b(mild|moderate|severe|worse|worst|better|improving|same|constant|on and off|comes and goes)\b",
            combined_text,
        )
    )
    symptom_keywords = {
        "fever", "cough", "headache", "vomiting", "nausea", "diarrhea", "stomach",
        "pain", "rash", "sore throat", "weakness", "dizziness", "body pains", "runny nose",
    }
    observed_symptoms = {s for s in symptom_keywords if s in combined_text}
    return {
        "user_messages": user_messages,
        "latest_message": latest_message,
        "lowered": latest_message.lower(),
        "combined_text": combined_text,
        "has_duration": has_duration,
        "has_severity": has_severity,
        "has_multiple_symptoms": len(observed_symptoms) >= 2,
    }


def should_auto_handoff_to_pharmacist(translated_messages: list[dict], ai_reply: str = "") -> bool:
    analysis = analyze_conversation_state(translated_messages)
    combined_text = f"{analysis['combined_text']} {ai_reply.lower()}".strip()
    explicit_handoff_request = any(
        phrase in combined_text
        for phrase in {
            "send to pharmacist", "talk to pharmacist", "pharmacist review",
            "review by pharmacist", "case review",
        }
    )
    enough_clinical_detail = (
        analysis["has_duration"]
        and analysis["has_multiple_symptoms"]
        and (analysis["has_severity"] or len(analysis["user_messages"]) >= 3)
    )
    return explicit_handoff_request or enough_clinical_detail


# ── fallback builders ────────────────────────────────────────────────
def build_local_chat_fallback(
    translated_messages: list[dict],
    input_language: str,
    relevant_pdf_context: str,
) -> str:
    analysis = analyze_conversation_state(translated_messages)
    latest_message = analysis["latest_message"]
    lowered = analysis["lowered"]

    urgent_keywords = {
        "difficulty breathing", "shortness of breath", "chest pain", "convulsion",
        "seizure", "confusion", "unconscious", "severe dehydration", "yellow eyes",
        "dark urine", "blood in stool", "coughing blood",
    }
    if any(keyword in lowered for keyword in urgent_keywords):
        if input_language == "twi":
            return (
                "Ayoo, sorry paa sɛ woretwa mu saa. Saa nsɛnkyerɛnne yi betumi ayɛ asiane, "
                "enti kɔ ayaresabea anaa frɛ emergency ntɛm. Wobɛtumi akɔ ayaresabea mprempren?"
            )
        return (
            "I am really sorry you are dealing with this. Those symptoms can be dangerous, "
            "so please go to the nearest hospital or seek emergency care now. "
            "Are you able to get urgent medical help right away?"
        )

    context_line = ""
    if relevant_pdf_context:
        context_line = " I can still guide you using the local clinical guideline notes I already have available."

    has_duration = analysis["has_duration"]
    has_severity = analysis["has_severity"]
    has_multiple_symptoms = analysis["has_multiple_symptoms"]

    if input_language == "twi":
        if not has_duration:
            return f"Ayoo, sorry paa sɛ woretɔ saa.{context_line} Mepa wo kyɛw, bere bɛn na yareɛ no fii ase?"
        if not has_severity:
            return f"Meda wo ase sɛ woka kyerɛ me.{context_line} Seesei, ɛreyɛ den anaa ɛretew?"
        if not has_multiple_symptoms:
            return f"Me te ase.{context_line} Yareɛ yi akyi no, nsɛnkyerɛnne foforo bɛn na woahu bio?"
        return f"Mehu sɛ wei haw wo paa.{context_line} Mepa wo kyɛw, saa bere yi mu no, dɛn na ɛhaw wo paa sen biara?"

    if not has_duration:
        return f"I'm sorry you're feeling this way.{context_line} To guide you safely, when exactly did these symptoms start?"
    if not has_severity:
        return f"Thanks for telling me that.{context_line} Has it been getting better, worse, or staying about the same?"
    if not has_multiple_symptoms:
        return f"I hear you.{context_line} Besides that main symptom, what other symptoms have you noticed?"
    if latest_message:
        return f"That sounds really uncomfortable.{context_line} What is bothering you the most right now?"
    return (
        f"I'm sorry you're feeling unwell.{context_line} "
        "Please tell me when the symptoms started so I can guide you step by step."
    )


def build_fallback_consult_summary(translated_messages: list[dict], input_language: str) -> str:
    analysis = analyze_conversation_state(translated_messages)
    summary_source = " ".join(analysis["user_messages"][-3:]).strip()
    short_summary = summary_source[:220] if summary_source else "the reported symptoms"
    if input_language == "twi":
        return (
            "Meda wo ase. Makaboa nsɛm a wode ama no nyinaa ano. "
            f"Nsɛm titiriw a mede rekɔma oduruyɛfo no ne: {short_summary}. "
            "Mede bɛkɔma oduruyɛfo a ɔwɔ tumi ahwɛ mu na ɔnyɛ ayaresa ho gyinae."
        )
    return (
        "Thank you. I have gathered the key clinical details. "
        f"The summary for the pharmacist is: {short_summary}. "
        "I will send this to a licensed pharmacist to review and decide the appropriate treatment."
    )


# ── case‑creation helpers ────────────────────────────────────────────
def infer_urgency_level(text: str) -> str:
    lowered = (text or "").lower()
    urgent_terms = ["difficulty breathing", "shortness of breath", "chest pain", "confusion", "convulsion", "unconscious", "bleeding"]
    priority_terms = ["worse", "severe", "high fever", "vomiting", "dehydration"]
    if any(term in lowered for term in urgent_terms):
        return "urgent"
    if any(term in lowered for term in priority_terms):
        return "priority"
    return "routine"


def detect_symptom_metadata(user_messages: list[str]) -> tuple[str, str]:
    text = " ".join(user_messages).lower()
    area_map = {
        "head": ["head", "headache", "dizziness", "brain"],
        "throat": ["throat", "neck", "swallow"],
        "chest": ["chest", "breathing", "cough", "lungs"],
        "abdomen": ["stomach", "abdomen", "belly", "vomiting", "diarrhea"],
        "lower": ["urine", "urinary", "pelvic", "lower abdomen", "menstrual"],
        "arm": ["arm", "joint", "shoulder", "elbow", "wrist"],
        "leg": ["leg", "knee", "swelling", "thigh"],
        "foot": ["foot", "ankle", "toe", "heel"],
    }
    type_map = {
        "pain": ["pain", "ache", "hurt", "cramp"],
        "rash": ["rash", "itch", "skin"],
        "breathing": ["breathing", "cough", "shortness of breath"],
        "digestive": ["vomiting", "diarrhea", "nausea", "stomach"],
        "fever": ["fever", "temperature", "feverish"],
        "wound": ["wound", "cut", "burn", "bleeding"],
    }
    symptom_area = next(
        (area for area, terms in area_map.items() if any(term in text for term in terms)), ""
    )
    symptom_type = next(
        (kind for kind, terms in type_map.items() if any(term in text for term in terms)), ""
    )
    return symptom_area, symptom_type


def build_patient_clinical_profile_snapshot(db: Session, user_id: int | None) -> str:
    if not user_id:
        return "No patient clinical profile was shared."
    patient = db.query(models.User).filter(models.User.id == user_id).first()
    if not patient:
        return "No patient clinical profile was shared."
    profile = patient.profile
    medical = patient.medical
    emergency = patient.emergency
    active_medications = [
        med for med in patient.medications
        if (med.status or "").lower() in {"active", "ongoing", "current"}
    ]
    medication_source = active_medications if active_medications else list(patient.medications)
    medications = ", ".join(
        filter(
            None,
            [
                f"{med.name} {med.dose}".strip() + (f" ({med.freq})" if med.freq else "")
                for med in medication_source if med.name
            ],
        )
    ) or "None reported"
    conditions = ", ".join(c.name for c in patient.conditions if c.name) or "None reported"
    allergies = ", ".join(a.name for a in patient.allergies if a.name) or "None reported"
    full_name = " ".join(
        part for part in [profile.first_name if profile else "", profile.last_name if profile else ""] if part
    ).strip() or patient.username or patient.email or "Not provided"

    sections = [
        f"Patient: {full_name}",
        f"DOB: {profile.dob if profile and profile.dob else 'Not provided'}",
        f"Gender: {profile.gender if profile and profile.gender else 'Not provided'}",
        f"Blood type: {profile.blood_type if profile and profile.blood_type else 'Not provided'}",
        f"Phone: {profile.phone if profile and profile.phone else 'Not provided'}",
        f"City: {profile.city if profile and profile.city else 'Not provided'}",
        f"Address: {profile.address if profile and profile.address else 'Not provided'}",
        f"Conditions: {conditions}",
        f"Allergies: {allergies}",
        f"Current medications: {medications}",
        f"Smoking: {medical.smoking if medical and medical.smoking else 'Not reported'}",
        f"Alcohol: {medical.alcohol if medical and medical.alcohol else 'Not reported'}",
        f"Clinical notes: {medical.notes if medical and medical.notes else 'None'}",
        f"Emergency alert: {emergency.alert if emergency and emergency.alert else 'None'}",
    ]
    return " | ".join(sections)


def build_pharmacist_case_details(
    translated_messages: list[dict],
    ai_summary: str,
    matched_drugs: list[dict],
    final_matches: list[dict] | None = None,
    relevant_pdf_context: str = "",
) -> str:
    user_points = [
        message["content"].strip()
        for message in translated_messages
        if message.get("role") == "user" and message.get("content", "").strip()
    ]
    symptom_history = " | ".join(user_points[-4:])[:500]
    pharmacist_guidance: list[str] = []
    for drug in matched_drugs[:3]:
        name = drug.get("name") or "Unspecified option"
        indication = drug.get("indication") or "General indication"
        category = drug.get("category") or "General category"
        pharmacist_guidance.append(f"{name} ({category}; {indication})")
    final_guidance: list[str] = []
    for match in (final_matches or [])[:3]:
        disease = match.get("disease") or "Unspecified condition"
        drug = match.get("drug") or "Unspecified drug"
        final_guidance.append(f"{disease} -> {drug}")
    dataset_sections: list[str] = []
    if pharmacist_guidance:
        dataset_sections.append(f"medicine_dataset.csv: {', '.join(pharmacist_guidance)}")
    if final_guidance:
        dataset_sections.append(f"final.csv: {', '.join(final_guidance)}")
    guidance_text = " | ".join(dataset_sections) if dataset_sections else "No specific dataset guidance matched."
    pdf_text = relevant_pdf_context[:1000] if relevant_pdf_context else "No specific PDF guidance matched."
    return (
        f"### AI CLINICAL INTAKE SUMMARY\n{ai_summary}\n\n"
        f"--- \n"
        f"**Recent patient statements:** {symptom_history or 'Not captured'} \n"
        f"**Dataset guidance for review:** {guidance_text} \n"
        f"**PDF guidance for review:** {pdf_text}"
    )


def log_case_event(case: models.PrescriptionHistory, actor_role: str, actor_name: str, action: str, note: str = ""):
    case.events.append(
        models.CaseEvent(actor_role=actor_role, actor_name=actor_name, action=action, note=note)
    )


def create_case_record(
    db: Session,
    user_id: int | None,
    translated_messages: list[dict],
    ai_summary: str,
    matched_drugs: list[dict],
    final_matches: list[dict] | None = None,
    relevant_pdf_context: str = "",
    actor_note: str = "Case created from AI triage intake.",
) -> models.PrescriptionHistory:
    user_messages = [
        message["content"].strip()
        for message in translated_messages
        if message.get("role") == "user" and message.get("content", "").strip()
    ]
    symptom_area, symptom_type = detect_symptom_metadata(user_messages)
    
    # Use the detailed AI summary for the main case summary
    case_summary = ai_summary[:2000] 
    
    patient_clinical_profile = build_patient_clinical_profile_snapshot(db, user_id)
    case_details = (
        build_pharmacist_case_details(
            translated_messages=translated_messages,
            ai_summary=ai_summary,
            matched_drugs=matched_drugs,
            final_matches=final_matches,
            relevant_pdf_context=relevant_pdf_context,
        )
        + f" || Patient clinical profile for pharmacist review: {patient_clinical_profile}"
    )
    case = models.PrescriptionHistory(
        user_id=user_id,
        pharmacist_id=None,
        drug_name="Pharmacist review required",
        details=case_details,
        patient_message=user_messages[-1] if user_messages else "",
        case_summary=case_summary,
        ai_summary=ai_summary[:2000],
        urgency_level=infer_urgency_level(f"{case_summary} {ai_summary}"),
        follow_up_status="awaiting_acceptance",
        symptom_area=symptom_area,
        symptom_type=symptom_type,
        status="Pending",
    )
    log_case_event(case, "system", "RxAI", "case_created", actor_note)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


# ── unified chat processor ──────────────────────────────────────────
def process_chat(
    messages: list[dict],
    db: Session,
    user_id: int | None = None,
    image_data: str | None = None,
) -> dict:
    """
    Process a list of chat messages through the full triage pipeline.

    Returns a dict with keys: reply, drugs, consulting, error, case_id
    """
    # Detect Twi
    input_language = "en"
    for m in messages:
        if m["role"] == "user" and translate_twi_to_english(m["content"]):
            input_language = "twi"
            break

    translated_messages: list[dict] = []
    for m in messages:
        if m["role"] == "user" and input_language == "twi":
            translated = translate_twi_to_english(m["content"])
            translated_messages.append({"role": "user", "content": translated or m["content"]})
        else:
            translated_messages.append(m)

    relevant_pdf_context = get_relevant_pdf_context(translated_messages)

    prompt_parts = [SYSTEM_PROMPT]
    if relevant_pdf_context:
        prompt_parts.append(
            "Use the following PDF guideline excerpts when they are relevant to the user question. "
            "Prefer these excerpts over guessing.\n\n"
            f"{relevant_pdf_context}"
        )
    if input_language == "twi":
        prompt_parts.append(
            "Answer in Twi in a caring, clear way. If you need to translate medical terms, "
            "keep them understandable for non-English speakers. Still follow the conversation "
            "rules and use [CONSULT_READY] when ready."
        )

    case_id: int | None = None

    final_messages = [{"role": "system", "content": "\n\n".join(prompt_parts)}] + translated_messages
    
    if image_data and final_messages:
        last_msg = final_messages[-1]
        text_content = last_msg["content"]
        last_msg["content"] = [
            {"type": "text", "text": text_content},
            {"type": "image_url", "image_url": {"url": image_data}}
        ]

    try:
        response = openai_client.chat.completions.create(
            model=MODEL_NAME,
            messages=final_messages,
            max_tokens=1000,
        )
        reply = response.choices[0].message.content

        if input_language == "twi":
            translation_response = openai_client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Translate the following English medical advice to fluent Twi. "
                            "Keep it natural, caring, and concise. Use simple terms for medical concepts. "
                            "If the text contains [CONSULT_READY], keep that marker exactly as is."
                        ),
                    },
                    {"role": "user", "content": reply},
                ],
                max_tokens=1000,
            )
            reply = translation_response.choices[0].message.content

        marker_handoff = "[CONSULT_READY]" in reply
        local_handoff = should_auto_handoff_to_pharmacist(translated_messages, reply)
        is_consulting = marker_handoff or local_handoff
        matched_drugs: list[dict] = []

        if is_consulting:
            reply = reply.replace("[CONSULT_READY]", "").strip()
            if not marker_handoff:
                reply = build_fallback_consult_summary(
                    translated_messages=translated_messages, input_language=input_language
                )
            all_user_text = " ".join(m["content"] for m in translated_messages if m["role"] == "user")
            search_text = all_user_text + " " + reply
            matched_drugs = search_medicine_dataset(search_text, limit=4)
            final_matches = search_final_dataset(search_text, limit=4)

            # --- GENERATE DETAILED CLINICAL REPORT ---
            detailed_report = generate_detailed_summary(translated_messages)

            case = create_case_record(
                db=db,
                user_id=user_id,
                translated_messages=translated_messages,
                ai_summary=detailed_report, # Use the detailed report as the primary summary
                matched_drugs=matched_drugs,
                final_matches=final_matches,
                relevant_pdf_context=relevant_pdf_context,
                actor_note="Case created from model-driven triage handoff.",
            )
            case_id = case.id
            reply = (
                f"{reply}\n\n"
                "I have prepared your case summary and sent it for licensed pharmacist review. "
                "The pharmacist will assess the information and decide the appropriate treatment."
            )

        return {
            "reply": reply,
            "drugs": None,
            "consulting": is_consulting,
            "error": None,
            "case_id": case_id,
        }
    except Exception as e:
        should_handoff = should_auto_handoff_to_pharmacist(translated_messages)
        if should_handoff:
            fallback_reply = build_fallback_consult_summary(
                translated_messages=translated_messages, input_language=input_language
            )
            search_text = (
                " ".join(m["content"] for m in translated_messages if m["role"] == "user")
                + " "
                + fallback_reply
            )
            matched_drugs = search_medicine_dataset(search_text, limit=4)
            final_matches = search_final_dataset(search_text, limit=4)
            case = create_case_record(
                db=db,
                user_id=user_id,
                translated_messages=translated_messages,
                ai_summary=fallback_reply,
                matched_drugs=matched_drugs,
                final_matches=final_matches,
                relevant_pdf_context=relevant_pdf_context,
                actor_note="Case created from fallback triage handoff.",
            )
            case_id = case.id
            fallback_reply = f"{fallback_reply}\n\nYour case has been submitted for licensed pharmacist review."
        else:
            fallback_reply = build_local_chat_fallback(
                translated_messages=translated_messages,
                input_language=input_language,
                relevant_pdf_context=relevant_pdf_context,
            )
        return {
            "reply": fallback_reply,
            "drugs": None,
            "consulting": should_handoff,
            "error": str(e),
            "case_id": case_id,
        }


# ── streaming helper ─────────────────────────────────────────────────
def build_system_messages(messages: list[dict], image_data: str | None = None) -> list[dict]:
    """Build the full messages list (system prompt + history) for streaming endpoints."""
    input_language = "en"
    for m in messages:
        if m["role"] == "user" and translate_twi_to_english(m["content"]):
            input_language = "twi"
            break

    translated: list[dict] = []
    for m in messages:
        if m["role"] == "user" and input_language == "twi":
            t = translate_twi_to_english(m["content"])
            translated.append({"role": "user", "content": t or m["content"]})
        else:
            translated.append(m)

    relevant_pdf_context = get_relevant_pdf_context(translated)
    prompt_parts = [SYSTEM_PROMPT]
    if relevant_pdf_context:
        prompt_parts.append(
            "Use the following PDF guideline excerpts when relevant:\n\n" + relevant_pdf_context
        )
    if input_language == "twi":
        prompt_parts.append(
            "Answer in Twi. Keep it natural and understandable. Use [CONSULT_READY] when ready."
        )

    system_content = "\n\n".join(prompt_parts)
    final_messages = [{"role": "system", "content": system_content}] + translated

    if image_data and final_messages:
        last_msg = final_messages[-1]
        text_content = last_msg["content"]
        last_msg["content"] = [
            {"type": "text", "text": text_content},
            {"type": "image_url", "image_url": {"url": image_data}}
        ]
    
    return final_messages


# ── Abena AI translation ─────────────────────────────────────────────
import httpx as _httpx

ABENA_API_KEY = os.getenv("ABENA_API_KEY", "")
ABENA_TRANSLATE_URL = "https://abena.mobobi.com/playground/api/v1/translate/translate/"

ABENA_LANG_CODES = {
    "tw": "twi_Latn",
    "ha": "hau_Latn",
    "fr": "fra_Latn",
    "en": "eng_Latn",
}


def translate_with_abena(text: str, source_lang: str, target_lang: str) -> str | None:
    """Translate text using Abena AI REST API. Returns None on failure or missing key."""
    if not ABENA_API_KEY or not text.strip():
        return None
    src = ABENA_LANG_CODES.get(source_lang, source_lang)
    tgt = ABENA_LANG_CODES.get(target_lang, target_lang)
    try:
        resp = _httpx.post(
            ABENA_TRANSLATE_URL,
            json={"text": text, "source_lang": src, "target_lang": tgt},
            headers={"Authorization": f"Bearer {ABENA_API_KEY}", "Content-Type": "application/json"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("translation") or data.get("translated_text") or None
    except Exception:
        pass
    return None
