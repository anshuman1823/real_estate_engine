
import os
from dotenv import load_dotenv
import pickle as pkl
from langchain_openai import AzureChatOpenAI
from langchain_openai import OpenAI
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
import json
from langchain_community.retrievers import TavilySearchAPIRetriever
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from typing import List, Dict, Any
from helper_classes import SimulationOutput, EvaluatedStrategy, StrategyEvaluationList, UserInput, FinalReport

import os
from datetime import datetime
from dotenv import load_dotenv

# --- PDF Generation Library ---
# Note: You must install this library first: pip install fpdf2
from fpdf import FPDF

# Import your existing Pydantic models and LangChain components
# from your_project_file import FinalReport, ChatPromptTemplate, PydanticOutputParser, AzureChatOpenAI

# --- REVISED AND IMPROVED PDF GENERATION FUNCTION ---

def save_memo_as_pdf(report: 'FinalReport', filename: str = "simulation_memo.pdf"):
    """
    Creates a professionally formatted PDF file from the structured report object.
    This function now handles all formatting internally.

    Args:
        report: The structured FinalReport Pydantic object.
        filename: The name of the output PDF file.
    """
    
    class PDF(FPDF):
        def header(self):
            self.set_font("Helvetica", 'B', 14)
            self.cell(0, 10, "MEMORANDUM FOR THE RECORD", 0, 1, 'C')
            self.ln(5)

        def footer(self):
            # Position 2.5 cm from bottom
            self.set_y(-25)
            self.set_font("Helvetica", 'I', 7)
            
            # Draw a line above the disclaimer
            self.line(self.get_x(), self.get_y(), self.get_x() + 180, self.get_y())
            self.ln(2)

            # Disclaimer text
            disclaimer_text = (
                "Scoring Method Disclaimer:\n"
                "1. Individual scores (Impact, Speed, Cost-Risk) are generated on a scale of 0-10.\n"
                "2. The Weighted Overall Score for each strategy is calculated as: (Impact * 0.5) + (Speed * 0.3) + (Cost-Risk * 0.2).\n"
                "3. The final simulation score is the average of the top three strategies' overall scores, converted to a 0.0-1.0 scale."
            )
            # Changed alignment from 'C' to 'L' for left-alignment
            self.multi_cell(0, 3.5, disclaimer_text, 0, 'L')
            
            # Removed the page number marker

        def section_title(self, title: str):
            self.set_font("Helvetica", 'B', 12)
            self.set_fill_color(240, 240, 240) # Light grey background
            self.cell(0, 8, title, 0, 1, 'L', fill=True)
            self.ln(4)

        def section_body(self, body: str):
            self.set_font("Helvetica", '', 11)
            # fpdf2 with standard fonts handles basic UTF-8 characters,
            # but we write text directly to avoid encoding issues.
            self.multi_cell(0, 5, body)
            self.ln(6)

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25) # Increased bottom margin for footer
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.set_top_margin(25)

    # --- Memo Header ---
    pdf.set_font("Helvetica", 'B', 11)
    pdf.cell(20, 5, "TO:")
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(0, 5, "Interested Parties", 0, 1)

    pdf.set_font("Helvetica", 'B', 11)
    pdf.cell(20, 5, "FROM:")
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(0, 5, "Simulation & Strategy Unit", 0, 1)

    pdf.set_font("Helvetica", 'B', 11)
    pdf.cell(20, 5, "DATE:")
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(0, 5, datetime.now().strftime('%B %d, %Y'), 0, 1)

    pdf.set_font("Helvetica", 'B', 11)
    pdf.cell(20, 5, "SUBJECT:")
    pdf.set_font("Helvetica", '', 11)
    pdf.cell(0, 5, "Strategic Review for Knightsbridge Townhouse", 0, 1)
    pdf.ln(8)

    # --- Report Sections ---
    
    # 1. Diagnosis
    pdf.section_title("1. DIAGNOSIS")
    pdf.section_body(report.diagnosis_summary)

    # 2. Recommended Actions
    pdf.section_title("2. RECOMMENDED STRATEGIC ACTIONS")
    for i, action in enumerate(report.detailed_actions):
        pdf.set_font("Helvetica", 'B', 11)
        # Replaced the unicode bullet '•' with a standard asterisk '*'
        # to prevent encoding errors with default PDF fonts.
        pdf.multi_cell(0, 5, f"  * {action['name']}")
        pdf.set_font("Helvetica", '', 11)
        pdf.set_left_margin(22) # Indent the explanation
        pdf.multi_cell(0, 5, action['explanation'])
        pdf.set_left_margin(15) # Reset margin
        pdf.ln(3)

    # 3. Forecast Analysis
    pdf.section_title("3. STRATEGIC ANALYSIS & FORECAST")
    pdf.section_body(report.forecast_analysis)

    # 4. Behavioural Commentary
    pdf.section_title("4. COMMENTARY: AGENT & SELLER BEHAVIOUR")
    pdf.section_body(report.behavioural_commentary)

    # --- Output PDF ---
    try:
        # Let the fpdf2 library handle writing the file directly
        # by providing the filename. This avoids type errors.
        pdf.output(filename)
        print(f"✅ Memo successfully saved as '{filename}'")
    except Exception as e:
        print(f"❌ Error saving PDF: {e}")


# --- REVISED MAIN REPORT GENERATOR FUNCTION ---

def report_generator_fn(final_result):
    """
    Main function to orchestrate the final report generation.
    It calls the LLM to create the structured report object, then calls the PDF generator.
    """
    # NOTE: This function assumes your Pydantic models and LangChain components are defined
    # in the same scope or imported correctly.
    
    load_dotenv(os.path.join(os.getcwd(), ".env"))
    azure_api_key = os.getenv("AZURE_API_KEY")
    azure_endpoint = os.getenv("AZURE_ENDPOINT")

    llm = AzureChatOpenAI(
        azure_deployment="gpt-4",
        api_version="2024-05-01-preview",
        temperature=0.1,
        api_key = azure_api_key,
        azure_endpoint = azure_endpoint
    )

    # If you want to use LLM via OpenAI API
    # import getpass
    # if "OPENAI_API_KEY" not in os.environ:
    #     os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")
    # llm = OpenAI(model = "gpt-4o")

    report_parser = PydanticOutputParser(pydantic_object=FinalReport)

    report_generator_prompt = ChatPromptTemplate.from_template(
        """
        You are a professional real estate analyst and report writer. Your task is to synthesize all the data from a simulation engine into a single, comprehensive, and human-readable report memo.

        **Input Data from Simulation Engine**:
        - **Core Diagnosis**: {diagnosis_output}
        - **Structured Strategy Evaluations**: {structured_evaluation}
        - **Final Recommended Actions Summary**: {final_structured_output}
        - **Behavioural Commentary**: {behavioural_output}
        - **Raw Evaluation Text (for justifications)**: {evaluation_output}

        **Your Instructions**:

        1.  **Diagnosis Section**: Write a clear, concise paragraph for the `diagnosis_summary` field.
        2.  **Strategic Actions Section**: For the `detailed_actions` field, create a list of dictionaries (keys: 'name', 'explanation'). The 'explanation' should summarize what the action involves and why it's effective, drawing from the "pros".
        3.  **Forecast Analysis Section**: For the `forecast_analysis` field, write a detailed analysis. Start with the overall simulation score. Then, for each of the top 3 actions, state its name, overall score, and justify its Impact, Speed, and Cost-Risk scores using the raw text.
        4.  **Behavioural Commentary Section**: For the `behavioural_commentary` field, summarize the top 3 suggestions from the input text in a concise and clear manner.
        5.  **Final Output**: Assemble all these sections into a single JSON object that adheres to the format instructions.

        {format_instructions}
        """,
        partial_variables={"format_instructions": report_parser.get_format_instructions()}
    )

    report_generation_chain = report_generator_prompt | llm | report_parser

    # Run the report generation chain
    final_report_object = report_generation_chain.invoke(final_result)

    # The old text-generation function is no longer needed.
    # We pass the structured object directly to the new PDF writer.
    save_memo_as_pdf(final_report_object)