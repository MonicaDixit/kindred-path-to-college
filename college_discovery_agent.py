"""
College Discovery Agent
Combines enhanced ranking + case study learning
IMPROVED VERSION - Clearer instructions
"""

from base_agent import BaseAgent
from llm_client import OpenRouterClient
from college_tools_enhanced import ENHANCED_TOOLS
from case_study_retrieval import CASE_STUDY_TOOLS
from typing import Dict, Any

class CollegeDiscoveryAgent(BaseAgent):
    """Agent that helps students find colleges"""
    
    def __init__(self, llm_client: OpenRouterClient):
        # Combine all tools
        all_tools = {
            **ENHANCED_TOOLS,  # College ranking tools
            **CASE_STUDY_TOOLS  # Case study retrieval tools
        }
        
        super().__init__(
            name="CollegeDiscoveryAgent",
            llm_client=llm_client,
            tools=all_tools
        )
    
    def get_system_prompt(self) -> str:
        return """You are an expert college counselor helping students find colleges.

IMPORTANT: You MUST respond in this exact format for each action:

THOUGHT: [explain what you need to do]
ACTION: [tool name]
INPUT: {"parameter": "value"}

Available tools:
- retrieve_similar_cases: Find similar student cases
- get_major_specific_strategy: Get advice for a major
- search_colleges: Search for colleges
- rank_college_fit: Rank fit for a college
- get_challenge_specific_wisdom: Get advice for challenges

Your job:
1. Understand the student's profile
2. Find similar student cases
3. Get advice for their major
4. Rank colleges (call rank_college_fit for each)
5. Organize into reach/target/safety
6. Provide FINAL_ANSWER with recommendations

Always use THOUGHT/ACTION/INPUT format. When done, use:
FINAL_ANSWER: [your recommendation]"""

    def build_college_list(self, student_profile: Dict[str, Any], verbose: bool = False) -> str:
        """
        Main method to build a college list for a student
        
        Args:
            student_profile: Dict with name, gpa, sat, major, is_first_gen, etc.
            verbose: Print detailed output
        """
        
        # Build prompt for the agent
        prompt = f"""Build a college list for this student:

Name: {student_profile.get('name', 'Student')}
GPA: {student_profile.get('gpa', 'Unknown')}
SAT: {student_profile.get('sat_score', 'Unknown')}
Major: {student_profile.get('major', 'Undecided')}
First-Gen: {student_profile.get('is_first_gen', False)}
Financial Aid Needed: {student_profile.get('needs_financial_aid', False)}

Steps:
1. First, call retrieve_similar_cases to find similar students
2. Then call get_major_specific_strategy to understand what this major needs
3. Then call rank_college_fit for these colleges: stanford, berkeley, uw, cmu, mit, caltech
4. Organize results into REACH (3-4), TARGET (3-4), SAFETY (2-3)
5. Provide FINAL_ANSWER with complete recommendations

Remember: Use THOUGHT/ACTION/INPUT format for each step."""
        
        # Run the agent
        result = self.run(prompt, verbose=verbose)
        
        return result