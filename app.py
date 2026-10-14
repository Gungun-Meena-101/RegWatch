import os, re, json
import pdfplumber, streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
st.set_page_config(page_title="RegWatch", page_icon="📜", layout="centered")
KEY = os.environ.get("GEMINI_API_KEY") or st.secrets["GEMINI_API_KEY"]
client = genai.Client(api_key=KEY)
MODEL = "gemini-3.5-flash-lite"
CUR = {"text": ""}

def norm(s): return re.sub(r"[\s\-–]+", "", str(s)).lower()
def nums(s): return {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*\.?\d*", str(s))}

def verify_quote(quote: str) -> dict:
    """Check whether a quote exists in the circular text."""
    return {"verified": norm(quote) in norm(CUR["text"])}

PROMPT = """You are a compliance agent for a COMMERCIAL BANK in India.
Decide if the RBI circular applies to Commercial Banks (relevant=true for Commercial Banks,
all banks, or all regulated entities including them; false for NBFC, UCB, RRB, SFB, LAB,
Payments Banks, HFC, AIFI, PPI issuers, Lead Banks, FEMA/Authorised Dealer circulars).
Steps: 1) pick an exact evidence quote showing WHO the circular applies to
2) call verify_quote on it (fix it if not verified).
If relevant=true, also extract the concrete obligations the bank must follow, each with an
exact quote from the circular. Use ONLY numbers and dates that appear in the circular.
If there is no testable obligation (e.g. a withdrawal or repeal), return an empty list.
Answer with JSON only:
{"relevant": true/false, "confidence": 0-1,
 "category": "KYC|Capital|Credit|Deposits|Governance|Reporting|Payments|Other",
 "reason": "one sentence: why relevant or not",
 "summary": "max 3 lines", "evidence_quote": "...",
 "obligations": [{"action": "...", "condition": "...", "deadline": "...",
   "type": "mandatory|advisory", "evidence_quote": "exact sentence",
   "gherkin": "Given ... When ... Then ..."}]}

Circular:
"""

def analyse(text):
    CUR["text"] = text
    r = client.models.generate_content(
        model=MODEL, contents=PROMPT + text[:12000],
        config=types.GenerateContentConfig(tools=[verify_quote], temperature=0))
    return json.loads(re.search(r"\{.*\}", r.text, re.S).group())

st.title("📜 RegWatch")
st.caption("Agentic AI for RBI compliance: does this circular apply to Commercial Banks?")

pdf = st.file_uploader("Upload an RBI circular (PDF)", type="pdf")
if pdf and st.button("Analyse", type="primary"):
    with pdfplumber.open(pdf) as p:
        text = "\n".join(pg.extract_text() or "" for pg in p.pages)
    if len(text) < 200:
        st.error("Could not read text (scanned PDF?)."); st.stop()
    with st.spinner("Agent is reading the circular..."):
        try:
            o = analyse(text)
        except Exception as e:
            st.error(f"LLM error: {str(e)[:150]}"); st.stop()

    q = str(o.get("evidence_quote") or "")
    verified = bool(q) and norm(q) in norm(text)
    tnums = nums(text)

    rows, gherkins, bad_ob = [], [], 0
    for ob in (o.get("obligations") or []) if o.get("relevant") else []:
        qv = bool(ob.get("evidence_quote")) and norm(ob["evidence_quote"]) in norm(text)
        used = nums(ob.get("gherkin", "") + " " + ob.get("action", "") + " " + ob.get("condition", ""))
        nv = used.issubset(tnums)
        bad_ob += (not qv) or (not nv)
        rows.append({"Action": ob.get("action", ""), "Condition": ob.get("condition", ""),
                     "Deadline": ob.get("deadline", ""), "Type": ob.get("type", ""),
                     "Quote verified": "Yes" if qv else "No",
                     "Numbers verified": "Yes" if nv else "No"})
        gherkins.append(ob.get("gherkin", ""))

    review = (
        (not verified)
        or o.get("confidence", 0) < 1.0
        or len(q) < 35
        or bad_ob > 0
        or not re.search(r"\bbanks?\b|regulated entit", q, re.I)
    )

    if o["relevant"]: st.success("✅ Relevant for Commercial Banks")
    else: st.info("⚪ Not relevant for Commercial Banks")
    c1, c2, c3 = st.columns(3)
    c1.metric("Category", o.get("category", "-"))
    c2.metric("Confidence", o.get("confidence", "-"))
    c3.metric("Quote verified", "Yes" if verified else "No")
    st.subheader("Why?"); st.write(o.get("reason", ""))
    st.subheader("Summary"); st.write(o.get("summary", ""))
    st.subheader("Evidence from the circular"); st.markdown(f"> {q}")

    if o["relevant"]:
        st.subheader("Compliance checklist")
        if rows:
            st.table(rows)
            for i, g in enumerate(gherkins, 1):
                with st.expander(f"Gherkin scenario {i}"):
                    st.code(g.replace(" When", "\n  When").replace(" Then", "\n  Then")
                             .replace(" And", "\n  And"), language="gherkin", wrap_lines=True)
        else:
            st.caption("No testable obligation found in this circular.")
        if len(text) > 12000:
            st.caption("Note: only the first 12,000 characters were analysed.")

    if review:
        st.warning("🧑‍⚖️ Human review recommended (weak evidence, low confidence, or unverified checklist item).")
    else:
        st.caption("No human review flag.")

st.divider()
st.caption("Decision-support tool, not legal advice. Always verify with the original RBI circular.")