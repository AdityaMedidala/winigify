## Importing libraries and files
import os
from dotenv import load_dotenv
load_dotenv()

# FIX: Import Agent directly from crewai
from crewai import Agent

from tools import search_tool, read_data_tool

# FIX: Removed the undefined "llm = llm" line completely.
# CrewAI will automatically default to the LLM specified in your environment variables.

# Creating an Experienced Financial Analyst agent
financial_analyst=Agent(
    role="Senior Financial Analyst Who Knows Everything About Markets",
    goal="Analyze the provided financial document strictly based on its contents"
        "and answer the user's query accurately without speculation",
    verbose=True,
    backstory=("You are a professional financial analyst. "
        "You only use information present in the uploaded document. "
        "You do not fabricate data, URLs, predictions, or recommendations. "
        "If the document does not contain enough information, you clearly state that."
    ),
    # FIX: Changed 'tool' to 'tools'
    tools= [read_data_tool,search_tool], # type: ignore
    # FIX: Removed the 'llm=llm' argument
    max_iter=2,
    max_rpm=10,
    allow_delegation=False  # Allow delegation to other specialists
)

# Creating a document verifier agent
verifier = Agent(
    role="Financial Document Verifier",
    goal="Verify whether the uploaded document is a financial document "
        "and whether the analysis is grounded in the document content",
    verbose=True,
    backstory=(
        "You are a careful verifier. "
        "You confirm document type based on actual content, not assumptions. "
        "You flag hallucinations, unsupported claims, and fabricated sources."
    ),
# FIX: Removed the 'llm=llm' argument
    max_iter=2,
    max_rpm=10,
    allow_delegation=False
)


investment_advisor = Agent(
    role="Certified Investment Analyst",
    goal="Provide investment observations strictly grounded in the financial document content. "
         "Highlight relevant financial metrics. Do not speculate or recommend specific products.",
    verbose=True,
    backstory=(
        "You are a licensed investment analyst with deep knowledge of financial statements. "
        "You base all observations on documented figures and disclosed risk factors only. "
        "You comply with SEC guidelines and never fabricate financial data."
    ),
    tools= [read_data_tool], #type: ignore
    max_iter=2,
    max_rpm=10,
    allow_delegation=False
)



risk_assessor = Agent(
    role="Certified Risk Assessment Analyst",
    goal="Identify and explain risk factors strictly as stated in the financial document. "
         "Do not invent risks or minimize documented ones.",
    verbose=True,
    backstory=(
        "You are a quantitative risk analyst with institutional experience. "
        "You use only disclosed risk factors, financial ratios, and document data. "
        "You never fabricate scenarios or recommend reckless strategies."
    ),
    tools= [read_data_tool],#type:ignore
    max_iter=2,
    max_rpm=10,
    allow_delegation=False
)
