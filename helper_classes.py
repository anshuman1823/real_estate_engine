from pydantic import BaseModel, Field
from typing import List, Dict, Any

class SimulationOutput(BaseModel):
    """Defines the structured output for a real estate simulation."""
    
    diagnosis: str = Field(
        description="A brief analysis of the property's current situation."
    )
    
    strategic_actions: List[str] = Field(
        description="A list of recommended actions to achieve the goal."
    )
    
    simulation_score: float = Field(
        description="A score from 0.0 to 1.0 indicating the confidence in the strategy's success.",
        ge=0,  # ge means 'greater than or equal to' (from 'minimum': 0)
        le=1   # le means 'less than or equal to' (from 'maximum': 1)
    )

class EvaluatedStrategy(BaseModel):
    """Defines the structured analysis for a single real estate strategy."""
    strategy_name: str = Field(description="The title of the strategy specifying what it's about.")
    pros: List[str] = Field(description="A list of reasons why the strategy might succeed.")
    cons: List[str] = Field(description="A list of potential risks or failures.")
    impact_score: float = Field(description="Score for the strategy's potential impact (0-10).")
    speed_score: float = Field(description="Score for the strategy's speed of implementation (0-10).")
    cost_risk_score: float = Field(description="Score representing low cost and low risk (0-10).")
    overall_score: float = Field(description="The final weighted overall score (0-10).")


class StrategyEvaluationList(BaseModel):
    """A container for a list of all evaluated strategies."""
    evaluations: List[EvaluatedStrategy] = Field(description="A list of all evaluated strategies.")

class UserInput(BaseModel):
    scenario: str
    goal: str
    constraint: str

class FinalReport(BaseModel):
    """Defines the structured content for the final report memo."""
    diagnosis_summary: str = Field(description="A clear, concise paragraph explaining what is going wrong with the property sale.")
    detailed_actions: List[Dict[str, str]] = Field(description="A list of recommended actions, where each action is a dictionary with 'name' and 'explanation' keys.")
    forecast_analysis: str = Field(description="A detailed analysis of the forecast, including the probability of success and a breakdown of why the top strategies are likely to work, with justifications for their scores.")
    behavioural_commentary: str = Field(description="Commentary on the agent and seller behaviour to consider for the best strategy.")