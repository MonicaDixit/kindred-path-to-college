"""
Simplified College Discovery Agent
WORKING VERSION - Gets results without infinite loops
"""

from llm_client import OpenRouterClient
from college_tools_enhanced import search_colleges, rank_college_fit, get_college_guidance
from case_study_retrieval import retrieve_similar_cases, get_major_specific_strategy
from typing import Dict, Any
import json

class SimpleCollegeAgent:
    """Simplified agent that gets results directly"""
    
    def __init__(self, llm_client: OpenRouterClient):
        self.llm_client = llm_client
        self.tools = {
            "search_colleges": search_colleges,
            "rank_college_fit": rank_college_fit,
            "retrieve_similar_cases": retrieve_similar_cases,
            "get_major_specific_strategy": get_major_specific_strategy,
        }
    
    def build_college_list(self, student_profile: Dict[str, Any], verbose: bool = False) -> str:
        """Build college list in simple steps"""
        
        name = student_profile.get('name', 'Student')
        gpa = student_profile.get('gpa', 0)
        sat = student_profile.get('sat_score', 0)
        major = student_profile.get('major', 'Undecided')
        is_first_gen = student_profile.get('is_first_gen', False)
        
        if verbose:
            print(f"\n📊 Analyzing profile for {name}...")
        
        # STEP 1: Get similar cases
        if verbose:
            print(f"🔍 Finding similar student cases...")
        
        similar_cases = retrieve_similar_cases(
            student_major=major,
            student_challenges=[],
            is_first_gen=is_first_gen
        )
        
        similar_text = ""
        if similar_cases.get('similar_cases'):
            similar_text = f"Similar students who succeeded:\n"
            for case in similar_cases['similar_cases'][:2]:
                similar_text += f"\n• {case.get('student_name', 'Unknown')} ({case.get('major')})\n"
                similar_text += f"  - Strategies: {', '.join(case.get('strategies_worked', [])[:2])}\n"
        
        # STEP 2: Get major strategy
        if verbose:
            print(f"📚 Getting {major} strategy...")
        
        major_strategy = get_major_specific_strategy(major)
        
        strategy_text = f"\nFor {major} students, schools value:\n"
        if major_strategy.get('what_schools_value'):
            for item in major_strategy['what_schools_value'][:3]:
                strategy_text += f"• {item}\n"
        
        # STEP 3: Rank colleges
        colleges_to_rank = ['stanford', 'berkeley', 'uw', 'cmu', 'mit', 'caltech', 'ut-austin', 'uiuc']
        
        if verbose:
            print(f"🏫 Ranking colleges...")
        
        ranked = []
        for college_id in colleges_to_rank:
            try:
                fit = rank_college_fit(
                    college_id=college_id,
                    student_gpa=gpa,
                    student_sat=sat,
                    student_major=major,
                    is_first_gen=is_first_gen
                )
                ranked.append(fit)
            except Exception as e:
                if verbose:
                    print(f"  ⚠ Error ranking {college_id}: {str(e)[:50]}")
        
        # STEP 4: Organize by category
        reach = []
        target = []
        safety = []
        
        for college in ranked:
            if college['category'] == 'reach':
                reach.append(college)
            elif college['category'] == 'target':
                target.append(college)
            elif college['category'] == 'safety':
                safety.append(college)
        
        # Sort by fit score descending
        reach.sort(key=lambda x: x.get('fit_score', 0), reverse=True)
        target.sort(key=lambda x: x.get('fit_score', 0), reverse=True)
        safety.sort(key=lambda x: x.get('fit_score', 0), reverse=True)
        
        # STEP 5: Format recommendation
        recommendation = f"""
{'='*70}
COLLEGE RECOMMENDATION FOR {name.upper()}
{'='*70}

PROFILE:
• GPA: {gpa}
• SAT: {sat}
• Major: {major}
• First-Gen: {is_first_gen}

{similar_text}

{strategy_text}

{'='*70}
COLLEGE LIST
{'='*70}

REACH SCHOOLS (Low probability, but worth applying):
{self._format_colleges(reach[:3])}

TARGET SCHOOLS (Realistic chances):
{self._format_colleges(target[:4])}

SAFETY SCHOOLS (Likely admits):
{self._format_colleges(safety[:3])}

RECOMMENDATIONS:
1. Focus application efforts on TARGET schools (most likely to succeed)
2. Apply to 2-3 REACH schools for aspirational options
3. Apply to 2-3 SAFETY schools as reliable backups
4. For {major}: {self._get_first_tip(major_strategy)}
5. Write authentic essays showing genuine passion
6. Build projects or internships to strengthen profile

{'='*70}
"""
        
        return recommendation
    
    def _format_colleges(self, colleges: list) -> str:
        """Format college list for display"""
        if not colleges:
            return "  (None found)"
        
        text = ""
        for i, college in enumerate(colleges, 1):
            name = college.get('college', 'Unknown')
            score = college.get('fit_score', 0)
            confidence = college.get('confidence', '0%')
            
            text += f"\n{i}. {name}\n"
            text += f"   • Fit Score: {score}/100\n"
            text += f"   • Admission Probability: {confidence}\n"
            
            # Add first reasoning point
            reasons = college.get('reasoning', [])
            if reasons:
                text += f"   • {reasons[0]}\n"
        
        return text
    
    def _get_first_tip(self, strategy: Dict[str, Any]) -> str:
        """Get first tip from major strategy"""
        if strategy.get('what_schools_value'):
            return strategy['what_schools_value'][0]
        return "pursue relevant projects and internships"