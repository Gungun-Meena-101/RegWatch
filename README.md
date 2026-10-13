# RegWatch: Agentic AI for RBI Compliance
LLM agent that reads RBI circulars, decides whether they apply to Commercial Banks,
summarises them with a verified evidence quote, and flags uncertain cases for human review.

## Results (75 annotated circulars)
| Model | Accuracy |
|---|---|
| Keyword | 93% |
| TF-IDF + LR | 85% |
| LLM | 98.7% |
| Agent | 100% |

## Run
pip install -r requirements.txt
streamlit run app.py

Decision-support tool, not legal advice.