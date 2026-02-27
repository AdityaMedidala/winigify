from crewai import Crew, Process
from agents import financial_analyst, verifier, risk_assessor,investment_advisor
from task import analyze_financial_document, verification, risk_assessment,investment_analysis


def run_crew(query: str, file_path: str = "data/sample.pdf") -> str:
    """Runs the CrewAI crew synchronously. Called by both the Celery worker and main.py."""
    financial_crew = Crew(
        agents=[financial_analyst,verifier, investment_advisor, risk_assessor],
        tasks=[analyze_financial_document,verification, investment_analysis, risk_assessment],
        process=Process.sequential,
    )
    result = financial_crew.kickoff(inputs={"query": query, "file_path": file_path})
    return str(result)