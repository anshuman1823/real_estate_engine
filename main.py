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
from report_generator import report_generator_fn
import argparse

def format_docs(docs):
    return "\n\n".join(f"**Source Document {i+1}**:\n{doc.page_content}" for i, doc in enumerate(docs))

load_dotenv(os.path.join(os.getcwd(), ".env"))
azure_api_key = os.getenv("AZURE_API_KEY")
azure_endpoint = os.getenv("AZURE_ENDPOINT")

def simulation(input_data):

    llm = AzureChatOpenAI(
        azure_deployment="gpt-4",  # or your deployment
        api_version="2024-12-01-preview",  # or your api version
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
        api_key = azure_api_key,
        azure_endpoint = azure_endpoint
    )

    # If you want to use LLM via OpenAI API
    # import getpass
    # if "OPENAI_API_KEY" not in os.environ:
    #     os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")
    # llm = OpenAI(model = "gpt-4o")

    string_parser = StrOutputParser()
    pydantic_parser = PydanticOutputParser(pydantic_object=SimulationOutput)
    evaluation_list_parser = PydanticOutputParser(pydantic_object=StrategyEvaluationList)


    ############################################## Defining prompt templates #######################################################

    search_query_prompt = ChatPromptTemplate.from_template(
        """
        You are an expert at generating web search queries for real estate analysis.
        Based on the following scenario, create a list of 3-5 distinct and effective search queries to find the most current information for the year 2025.

        **Scenario**: "{scenario}"

        **Information Required**:
        1.  The overall economic state of the real estate market in that specific location (e.g., market trends, new construction, buyer sentiment).
            a. Market Price & Transaction Trends: Target official data like the UK House Price Index (HPI) for the specific city/postcode, analyze quarterly price changes, and track sales transaction volumes.
            b. Housing Supply & Inventory: Investigate the volume of current property listings ("inventory levels"), the rate of new listings coming to market, and the pipeline of new construction projects approved or underway.
            c. Buyer Demand & Sentiment: Find data on buyer activity, such as mortgage approval rates for the region, average time on market for properties, and the "sale-to-asking-price" ratio to gauge negotiation power.
            d. Local Economic Context: Assess how national economic factors like interest rates and inflation are affecting the local market, and find information on local rental yields as an indicator of investment health.
        2.  The average price or price range for the type of property mentioned.
        3. Average cost of property in that location.

        **Generate a list of search queries here (one query per line)**:
        """
    )

    analyst_prompt = ChatPromptTemplate.from_template(
        """
        You are an expert real estate analyst. Your task is to perform a detailed diagnosis of a property scenario.
        First, you MUST review the live market data provided below to ground your analysis in the most current information.
        Then, proceed with your step-by-step thinking.

        ---
        **Live Market Context from Web Search**:
        {market_context}
        ---

        **Property Scenario Details**:
        - **Scenario**: {scenario}
        - **Goal**: {goal}
        - **Constraint**: {constraint}

        Produce a detailed text analysis based on BOTH the live context and your internal knowledge. Do not suggest solutions yet.
        """
    )

    diagnosis_prompt = ChatPromptTemplate.from_template(
        """
        You are a master diagnostician. Your job is to read a detailed real estate analysis and identify the single, most critical issue.
        Synthesize the core problem into one concise sentence.

        **Full Analyst Report**:
        {analyst_output}

        **Concise Diagnosis (1 sentence)**:
        """
    )

    strategist_prompt = ChatPromptTemplate.from_template(
        """
        You are a creative real estate strategist. Based on the analysis and the core diagnosis, brainstorm a numbered list of diverse and actionable strategies.
        Consider pricing and financial strategies, marketing and exposure, agent representation/incentives, property staging/presentation. 
        Think outside the box. 

        **Core Diagnosis**: {diagnosis_output}

        **Full Analyst Report**:
        {analyst_output}

        **The strategies should be specific and actionable, and have exact numbers in them to keep them precise.
        Example of specific actionable strategies: "Reposition guide to £4.25M", "Switch to performance-led agent within 14 days", "Reframe marketing with withdrawn comp narrative".
        Brainstorm at least 5-7 potential strategies (as a numbered list)**:
        """
    )

    strategy_evaluator_prompt = ChatPromptTemplate.from_template(
        """
        You are a highly analytical real estate simulation engine. Your task is to rigorously evaluate a list of proposed strategies using a detailed, multi-criteria scoring framework.

        **Context**:
        - **Current Time**: Thursday, 24 July 2025. Location is Birmingham, UK.
        - **Core Diagnosis**: {diagnosis_output}
        - **Brainstormed Strategies from your strategist team**:
        {strategist_output}

        **Your Task**:
        For each "Brainstormed Strategy," provide a detailed evaluation. Follow this structure precisely:

        ---
        **Strategy**: [Name of the Strategy]
        **Analysis**:
        * **Pros (Why it might succeed)**:
            1. [Reason 1, considering current market conditions]
            2. [Reason 2]
            3. [Reason 3]
        * **Cons (Potential risks or failures)**:
            1. [Reason 1]
            2. [Reason 2]
            3. [Reason 3]
        
        **Scoring (0-10 scale)**:
        * **Impact Score**: [Assign a score based on its potential to achieve the main goal. Justify briefly.]
        * **Speed Score**: [Assign a score based on how quickly it will yield results. Justify briefly.]
        * **Cost-Risk Score**: [Assign a score representing low cost and low risk (10 = very cheap/safe). Justify briefly.]

        **Weighted Overall Score**: [Calculate the final score using the formula: (Impact * 0.5) + (Speed * 0.3) + (Cost-Risk * 0.2). Show the result, e.g., 7.5/10]
        ---

        Repeat this evaluation for every strategy provided. Produce only this text analysis. Do not add any summary or conclusion.
        """
    )

    evaluation_parser_prompt = ChatPromptTemplate.from_template(
        """
        You are a data extraction agent. Parse the block of text containing strategy evaluations and convert it into a structured JSON format.

        **Unstructured Evaluation Text**:
        {evaluation_output}

        {format_instructions}
        """,
        partial_variables={"format_instructions": evaluation_list_parser.get_format_instructions()}
    )

    output_generator_prompt = ChatPromptTemplate.from_template(
        """
        You are a data formatting agent. Your sole task is to take a detailed strategy evaluation and format it into a clean JSON output.

        **Input Data**:
        - **Core Diagnosis**: {diagnosis_output}
        - **Detailed Strategy Evaluation**:
        {structured_evaluation}

        **Your Instructions**:
        1.  Read the "Detailed Strategy Evaluation".
        2.  Identify the 3 strategies with the highest "Success Probability Score".
        3.  List the names of these top 3 strategies as the `strategic_actions`.
        4.  Calculate the final `simulation_score` by taking the **average** of the scores from your top 3 selected strategies and dividing the average by 10.
        5.  Use the "Core Diagnosis" as the value for the `diagnosis` field.
        6.  Provide your response ONLY in the required JSON format.

        {format_instructions}
        """,
        partial_variables={"format_instructions": pydantic_parser.get_format_instructions()}
    )

    behaviour_prompt = ChatPromptTemplate.from_template(
        """
        You are a behavioural psychologist specializing in high-stakes negotiations.
        Based on the property's diagnosis and the final recommended strategy, what key behaviours should the seller and their agent adopt or avoid?
        Focus on mindset, communication, and negotiation posture.

        **Property Diagnosis**: {diagnosis_output}
        **Final Chosen Strategy**: {final_structured_output}

        **Key Behavioural Recommendations (for seller/agent)**:
        """
    )

    #########################################################################################################################

    ############################################## Main Simulation Logic #######################################################
    #### LLM chains ####

    # Internet retriever to get real-time knowledge
    retriever = TavilySearchAPIRetriever(k=10)

    # --- Define the chains for each agent (same as before) ---
    context_retrieval_chain = search_query_prompt | llm | StrOutputParser() | retriever | format_docs
    analyst_chain = analyst_prompt | llm | string_parser
    diagnosis_chain = diagnosis_prompt | llm | string_parser
    strategist_chain = strategist_prompt | llm | string_parser
    strategy_evaluator_chain = strategy_evaluator_prompt | llm | string_parser
    evaluation_parser_chain = evaluation_parser_prompt | llm | evaluation_list_parser
    output_generator_chain = output_generator_prompt | llm | pydantic_parser
    behaviour_chain = behaviour_prompt | llm | string_parser


    # The rest of the chain builds upon this grounded context
    full_chain_with_search = RunnablePassthrough.assign(
        market_context=context_retrieval_chain
    ).assign(
        analyst_output=analyst_chain
    ).assign(
        diagnosis_output=diagnosis_chain
    ).assign(
        strategist_output=strategist_chain
    ).assign(
        evaluation_output=strategy_evaluator_chain
    ).assign(
        structured_evaluation=evaluation_parser_chain
    ).assign(
        final_structured_output=output_generator_chain
    ).assign(
        behavioural_output=behaviour_chain
    )
    print("🚀 Running the full simulation chain...")
    final_result = full_chain_with_search.invoke(input_data)
    print("✅ Chain execution complete.")
    
    print("Final output:")
    print(json.dumps(final_result['final_structured_output'].model_dump(), indent=2))

    with open("output.json", "w", encoding="utf-8") as outfile:
        json.dump(final_result['final_structured_output'].model_dump(), outfile, indent=2)

    with open("final_result.pkl", "wb") as file:
        pkl.dump(final_result, file)
        
    print("ouptut.json updated with the generated output.")

    report_generator_fn(final_result)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run simulation with JSON input.")
    parser.add_argument("json_file", help="Path to the input JSON file")

    args = parser.parse_args()

    # Load JSON file
    try:
        with open(args.json_file, "r", encoding="utf-8") as file:
            input_data = json.load(file)

        # Call the function with the dictionary
        simulation(input_data)

    except FileNotFoundError:
        print(f"Error: File '{args.json_file}' not found.")
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON file. {e}")