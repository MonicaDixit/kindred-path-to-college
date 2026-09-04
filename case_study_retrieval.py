"""
Case Study Retrieval and Application
Teaches the agent to learn from real student stories
"""

import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from config import COLLEGE_DATA_FILE

@dataclass
class RelevantCaseStudy:
    """A case study relevant to current student"""
    name: str
    major: str
    relevance_score: float  # 0-1
    reason_relevant: str
    key_insights: List[str]
    college_strategy: Dict[str, Any]
    student_challenges: List[str]
    strategies_used: List[str]

class CaseStudyDatabase:
    """Database of real case studies for learning patterns"""
    
    def __init__(self, case_studies_file: Path = Path("case_studies_from_real_sources.json")):
        self.case_studies = []
        self.patterns = {}
        self.load_cases(case_studies_file)
    
    def load_cases(self, case_studies_file: Path):
        """Load case studies from JSON"""
        if not case_studies_file.exists():
            print(f"Warning: Case studies file not found at {case_studies_file}")
            return
        
        with open(case_studies_file, 'r') as f:
            data = json.load(f)
            self.case_studies = data.get('case_studies', [])
            self.patterns = data.get('patterns_and_insights', {})
    
    def find_relevant_cases(self, 
                           student_major: Optional[str] = None,
                           student_challenges: Optional[List[str]] = None,
                           student_demographics: Optional[Dict[str, str]] = None,
                           max_results: int = 3) -> List[RelevantCaseStudy]:
        """
        Find case studies relevant to a student's profile
        
        Args:
            student_major: Student's major of interest
            student_challenges: List of challenges (weak transcript, low test scores, etc.)
            student_demographics: Demographics (first_gen, international, etc.)
            max_results: Max case studies to return
        """
        
        scored_cases = []
        
        for case in self.case_studies:
            score = 0
            reason = []
            
            # 1. Major match (highest priority)
            if student_major and case.get('major'):
                case_majors = [case.get('major').lower()]
                if student_major.lower() in case_majors:
                    score += 0.4
                    reason.append(f"Same major ({student_major})")
                # Related majors
                elif self._majors_related(student_major, case.get('major')):
                    score += 0.2
                    reason.append(f"Related major ({case.get('major')})")
            
            # 2. Challenge match
            if student_challenges and case.get('academic_profile'):
                case_challenges = case.get('academic_profile', {}).get('challenges', [])
                for student_challenge in student_challenges:
                    for case_challenge in case_challenges:
                        if self._challenges_related(student_challenge, case_challenge):
                            score += 0.2
                            reason.append(f"Overcame similar challenge: {case_challenge}")
            
            # 3. Demographic match
            if student_demographics:
                if student_demographics.get('first_gen') and case.get('id') in [
                    'upenn_huntsman_dual_degree',  # Asian American first-gen proxy
                    'cultural_travel_narrative'  # Likely first-gen
                ]:
                    score += 0.2
                    reason.append("First-generation student (like you)")
                
                if student_demographics.get('asian_american') and case.get('id') == 'carnegie_hall_cellist_coder':
                    score += 0.3
                    reason.append("Asian American student story")
            
            if score > 0:
                scored_cases.append({
                    'case': case,
                    'score': score,
                    'reason': ' + '.join(reason)
                })
        
        # Sort by relevance score
        scored_cases.sort(key=lambda x: x['score'], reverse=True)
        
        # Convert to RelevantCaseStudy objects
        results = []
        for item in scored_cases[:max_results]:
            case = item['case']
            
            insights = case.get('insights_for_agent', [])
            strategies = case.get('strategy_applied', [])
            challenges = case.get('academic_profile', {}).get('challenges', [])
            
            college_strategy = case.get('college_fit_indicators', {})
            
            results.append(RelevantCaseStudy(
                name=case.get('name'),
                major=case.get('major'),
                relevance_score=item['score'],
                reason_relevant=item['reason'],
                key_insights=insights[:3],  # Top 3 insights
                college_strategy=college_strategy,
                student_challenges=challenges,
                strategies_used=strategies
            ))
        
        return results
    
    def _majors_related(self, major1: str, major2: str) -> bool:
        """Check if two majors are related"""
        related_groups = {
            'cs': ['computer science', 'cs', 'computer engineering', 'machine learning', 'ai'],
            'stem': ['engineering', 'physics', 'chemistry', 'biology', 'mathematics'],
            'business': ['business', 'economics', 'finance', 'entrepreneurship'],
            'pre_med': ['medicine', 'pre-med', 'biology', 'chemistry', 'healthcare'],
            'humanities': ['liberal arts', 'english', 'history', 'philosophy'],
        }
        
        major1_lower = major1.lower()
        major2_lower = major2.lower()
        
        for group, majors in related_groups.items():
            if major1_lower in majors and major2_lower in majors:
                return True
        
        return False
    
    def _challenges_related(self, challenge1: str, challenge2: str) -> bool:
        """Check if two challenges are related"""
        challenge_groups = {
            'academic': ['weak transcript', 'low gpa', 'blemishes', 'poor grades'],
            'test_scores': ['low test scores', 'low sat', 'weak act'],
            'extracurricular': ['lack of activities', 'scattered', 'no leadership'],
            'profile': ['average student', 'ordinary', 'not unique'],
            'background': ['low income', 'first gen', 'immigrant', 'disadvantaged'],
        }
        
        for group, challenges in challenge_groups.items():
            if any(c in challenge1.lower() for c in challenges) and \
               any(c in challenge2.lower() for c in challenges):
                return True
        
        return False
    
    def get_patterns_for_major(self, major: str) -> Dict[str, List[str]]:
        """Get admission patterns and insights for a specific major"""
        patterns = self.patterns.get('major_specific_patterns', {})
        
        major_lower = major.lower()
        if 'cs' in major_lower or 'computer' in major_lower:
            return patterns.get('cs_students', [])
        elif 'business' in major_lower or 'econ' in major_lower:
            return patterns.get('business_students', [])
        elif 'med' in major_lower or 'pre-med' in major_lower:
            return patterns.get('pre_med_students', [])
        elif any(s in major_lower for s in ['engineering', 'physics', 'chemistry', 'biology']):
            return patterns.get('stem_students', [])
        else:
            return patterns.get('liberal_arts_students', [])
    
    def get_general_wisdom(self) -> List[str]:
        """Get general college selection wisdom from patterns"""
        return self.patterns.get('college_selection_wisdom', [])

# Global database
case_db = CaseStudyDatabase()

# ============================================================================
# AGENT INTEGRATION TOOLS
# ============================================================================

def retrieve_similar_cases(student_major: Optional[str] = None,
                          student_challenges: Optional[List[str]] = None,
                          is_first_gen: bool = False) -> Dict[str, Any]:
    """
    Retrieve case studies similar to student's profile
    (Tool the agent can call)
    """
    
    demographics = {}
    if is_first_gen:
        demographics['first_gen'] = True
    
    similar_cases = case_db.find_relevant_cases(
        student_major=student_major,
        student_challenges=student_challenges,
        student_demographics=demographics,
        max_results=3
    )
    
    if not similar_cases:
        return {
            "status": "No directly similar cases found",
            "general_wisdom": case_db.get_general_wisdom()
        }
    
    formatted_cases = []
    for case in similar_cases:
        formatted_cases.append({
            "student_name": case.name,
            "major": case.major,
            "relevance": f"{case.relevance_score*100:.0f}%",
            "why_relevant": case.reason_relevant,
            "they_faced": case.student_challenges[:2],
            "strategies_worked": case.strategies_used[:2],
            "key_insight": case.key_insights[0] if case.key_insights else "N/A",
            "college_strategy": {
                "reach_schools": case.college_strategy.get('reach_schools', 'N/A'),
                "target_schools": case.college_strategy.get('target_schools', 'N/A')
            }
        })
    
    return {
        "similar_cases": formatted_cases,
        "general_wisdom": case_db.get_general_wisdom()
    }

def get_major_specific_strategy(major: str) -> Dict[str, Any]:
    """
    Get strategies and patterns specific to a major
    """
    
    patterns = case_db.get_patterns_for_major(major)
    
    return {
        "major": major,
        "what_schools_value": patterns,
        "general_college_wisdom": case_db.get_general_wisdom(),
        "what_doesnt_work": case_db.patterns.get('what_doesnt_work', [])
    }

def get_challenge_specific_wisdom(challenge: str) -> Dict[str, Any]:
    """
    Get wisdom for overcoming specific challenges
    """
    
    # Find cases that overcame this challenge
    relevant_cases = []
    for case in case_db.case_studies:
        case_challenges = case.get('academic_profile', {}).get('challenges', [])
        if any(challenge.lower() in c.lower() for c in case_challenges):
            relevant_cases.append({
                "student": case.get('name'),
                "their_challenge": [c for c in case_challenges if challenge.lower() in c.lower()][0],
                "how_they_overcome": case.get('strategy_applied', []),
                "outcome": case.get('outcomes', {}).get('lesson', 'Successful admission')
            })
    
    return {
        "challenge": challenge,
        "cases_that_overcame_it": relevant_cases,
        "general_approach": f"Focus on compensating through narrative and other strengths. {challenge} is not a dealbreaker at holistic-review schools.",
        "what_worked": [
            "Strong essays explaining the challenge",
            "Demonstrated growth or learning",
            "Other areas of strength (activities, test scores, etc.)",
            "Unique perspective or background"
        ]
    }

# ============================================================================
# TOOL EXPORTS
# ============================================================================

CASE_STUDY_TOOLS = {
    "retrieve_similar_cases": retrieve_similar_cases,
    "get_major_specific_strategy": get_major_specific_strategy,
    "get_challenge_specific_wisdom": get_challenge_specific_wisdom,
}

# Example usage
if __name__ == "__main__":
    # Test retrieval
    print("\n=== Similar Cases for CS Student with Moderate Test Scores ===")
    result = retrieve_similar_cases(
        student_major="Computer Science",
        student_challenges=["low test scores", "need to differentiate"],
        is_first_gen=False
    )
    print(json.dumps(result, indent=2))
    
    print("\n=== CS-Specific Strategy ===")
    result = get_major_specific_strategy("Computer Science")
    print(json.dumps(result, indent=2))
    
    print("\n=== Overcoming Transcript Issues ===")
    result = get_challenge_specific_wisdom("weak transcript")
    print(json.dumps(result, indent=2))
