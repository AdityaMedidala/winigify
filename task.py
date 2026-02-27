## Importing libraries and files
from crewai import Task

from agents import financial_analyst, verifier,investment_advisor,risk_assessor

from tools import search_tool, read_data_tool

## Creating a task to help solve user's query
analyze_financial_document = Task(
    description= ("Use the 'Read Financial Document' tool ONCE to read the document at {file_path}. "
        "Answer the user's query: {query}. "
        "Base your response strictly on the document's contents. "
        "If information is missing or unclear, state that explicitly."),

    expected_output="A clear, structured answer grounded in the document. "
        "Include relevant figures or sections if applicable. "
        "Do not speculate or provide investment advice.",

    agent=financial_analyst,
    tools=[read_data_tool], # type: ignore
    async_execution=False,
)

investment_analysis = Task(
    description=(
        "Use the 'Read Financial Document' tool ONCE to read the document at {file_path}. "  # ADD THIS
        "Based on the financial analyst's document summary, identify key financial metrics "
        "relevant to investment considerations (e.g. revenue growth, margins, debt levels). "
        "User query: {query}. Ground every observation in the document — no speculation."
    ),
    expected_output=(
        "A structured investment observation section citing specific figures from the document. "
        "No external URLs, no fabricated data, no product recommendations."
    ),
    agent=investment_advisor,
    async_execution=False,
)

risk_assessment = Task(
    description=(
        "Use the 'Read Financial Document' tool ONCE to read the document at {file_path}. "  # ADD THIS
        "Based on the prior analysis, identify risk factors explicitly stated or implied "
        "in the financial document. User query: {query}. "
        "Do not invent risk scenarios not grounded in the document."
    ),
    expected_output=(
        "A risk summary citing specific document sections or figures. "
        "Include only documented risks. State clearly if the document lacks risk disclosures."
    ),
    agent=risk_assessor,
    async_execution=False,
)

    
verification = Task(
    description= ("Review the document and confirm whether it is a financial document. "
        "Verify that the analysis does not contain hallucinated data or unsupported claims."),
    expected_output= "A short verification stating whether the document is financial in nature "
        "and whether the analysis is valid and document-based.",
    agent=verifier,
    # No tools — intentional. Verifier reads analyst output, not the PDF.
    async_execution=False
)