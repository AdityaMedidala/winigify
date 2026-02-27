## Importing libraries and files
import os
from dotenv import load_dotenv
load_dotenv()

# FIX: Notice we are importing from 'crewai.tools', not 'crewai_tools'
from crewai.tools import tool

#added
from langchain_community.document_loaders import PyPDFLoader

# Fixed SerperDevTool import path for newer crewai_tools versions
from crewai_tools import SerperDevTool

#added
load_dotenv()


## Creating search tool
search_tool = SerperDevTool()



# FIX: Completely removed the "class FinancialDocumentTool:" wrapper.
# Added the @tool decorator so CrewAI recognizes it.
@tool("Read Financial Document")
def read_data_tool(file_path: str) -> str:
    """
    Tool to read text data from a PDF file.
    Pass the exact file_path of the PDF to read its contents.
    """
    try:
        # FIX: Replaced undefined 'Pdf' with PyPDFLoader
        loader = PyPDFLoader(file_path=file_path)
        docs = loader.load()

        full_report = ""
        for data in docs:
            # Clean and format the financial document data
            content = data.page_content

            # Remove extra whitespaces and format properly
            while "\n\n" in content:
                content = content.replace("\n\n", "\n")

            full_report += content + "\n"

        return full_report
    except Exception as e:
        return f"Error reading PDF file: {str(e)}"