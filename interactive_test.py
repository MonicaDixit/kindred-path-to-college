from simple_agent import SimpleCollegeAgent
from llm_client import OpenRouterClient

# Initialize agent
llm = OpenRouterClient()
agent = SimpleCollegeAgent(llm)

print("="*70)
print("COLLEGE ADVISOR - Interactive Test")
print("="*70)
print()

while True:
    print("\nEnter student profile (or 'quit' to exit):\n")
    
    try:
        name = input("Name: ").strip()
        if name.lower() == "quit":
            break
        
        gpa = float(input("GPA (e.g., 3.85): "))
        sat = int(input("SAT Score (e.g., 1520): "))
        major = input("Major (e.g., Computer Science): ").strip()
        
        first_gen = input("First-generation? (yes/no): ").strip().lower() == 'yes'
        needs_aid = input("Needs financial aid? (yes/no): ").strip().lower() == 'yes'
        
        # Build profile
        student = {
            "name": name,
            "gpa": gpa,
            "sat_score": sat,
            "major": major,
            "is_first_gen": first_gen,
            "needs_financial_aid": needs_aid
        }
        
        print("\nAnalyzing...")
        print("-"*70)
        
        result = agent.build_college_list(student, verbose=False)
        print(result)
        
    except ValueError:
        print("Invalid input. Please try again.")
    except Exception as e:
        print(f"Error: {e}")

print("\nGoodbye!")
EOF