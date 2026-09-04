"""
Kindred College Advisor - Simplified Main
WORKING VERSION - Direct execution, no LLM loops
"""

import sys
from llm_client import OpenRouterClient
from simple_agent import SimpleCollegeAgent
from config import DEMO_STUDENT

def main():
    """Main entry point"""
    
    print("=" * 70)
    print("KINDRED COLLEGE ADVISOR - AI-Powered College Selection")
    print("=" * 70)
    print()
    
    # Initialize
    print("Initializing agent...")
    try:
        llm = OpenRouterClient()
        agent = SimpleCollegeAgent(llm)
        print("✓ Agent ready\n")
    except Exception as e:
        print(f"✗ Error: {e}")
        return
    
    # Check for arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--demo":
            run_demo(agent, verbose=False)
        elif sys.argv[1] == "--demo-verbose" or sys.argv[1] == "--debug":
            run_demo(agent, verbose=True)
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print_help()
    else:
        interactive_mode(agent)

def run_demo(agent: SimpleCollegeAgent, verbose: bool = False):
    """Run demo"""
    
    print("=" * 70)
    print("DEMO: Building college list")
    print("=" * 70)
    print()
    
    print("Student Profile:")
    print(f"  Name: {DEMO_STUDENT['name']}")
    print(f"  GPA: {DEMO_STUDENT['gpa']}")
    print(f"  SAT: {DEMO_STUDENT['sat_score']}")
    print(f"  Major: {DEMO_STUDENT['major']}")
    print(f"  First-Gen: {DEMO_STUDENT['is_first_gen']}")
    print()
    
    print("Analyzing...")
    print("-" * 70)
    
    try:
        result = agent.build_college_list(DEMO_STUDENT, verbose=verbose)
        print(result)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def interactive_mode(agent: SimpleCollegeAgent):
    """Interactive mode"""
    
    print("Interactive Mode - Type 'demo' to run demo, 'quit' to exit\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == "quit":
                print("Goodbye!")
                break
            
            if user_input.lower() == "demo":
                run_demo(agent)
                continue
            
            print("\nCommand not recognized. Try 'demo' or 'quit'")
        
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break

def print_help():
    """Print help"""
    print("""
Usage: python main.py [COMMAND]

Commands:
  --demo        Run demo (fast!)
  --debug       Run demo with verbose output
  (none)        Interactive mode

Examples:
  python main.py --demo
  python main.py --debug
""")

if __name__ == "__main__":
    main()