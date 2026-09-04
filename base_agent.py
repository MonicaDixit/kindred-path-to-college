"""
Base Agent with ReAct Loop
IMPROVED VERSION - Better action parsing + debug output
"""

from typing import Dict, Any, Optional
from llm_client import OpenRouterClient
import json

class BaseAgent:
    """Base agent with ReAct (Reasoning + Acting) loop"""
    
    def __init__(self, name: str, llm_client: OpenRouterClient, tools: Dict[str, Any]):
        self.name = name
        self.llm_client = llm_client
        self.tools = tools
        self.trace = []
        self.max_iterations = 10
    
    def get_system_prompt(self) -> str:
        """Override in subclass"""
        return ""
    
    def think(self, context: str) -> str:
        """Call LLM to think about the problem"""
        system_prompt = self.get_system_prompt()
        
        messages = [
            {"role": "user", "content": context}
        ]
        
        response = self.llm_client.call(messages, system_prompt)
        return response
    
    def execute_tool(self, tool_name: str, input_data: Dict[str, Any]) -> Any:
        """Execute a tool"""
        
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' not found"
        
        try:
            tool = self.tools[tool_name]
            result = tool(**input_data)
            return result
        except Exception as e:
            return f"Error executing {tool_name}: {str(e)}"
    
    def run(self, user_input: str, verbose: bool = False) -> str:
        """
        Run the ReAct loop
        
        THINK → PARSE ACTION → EXECUTE TOOL → OBSERVE → REPEAT
        """
        
        context = user_input
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            
            if verbose:
                print(f"\n--- Iteration {iteration} ---")
            
            # STEP 1: THINK
            response = self.think(context)
            
            if verbose:
                print(f"\nLLM Raw Response:\n{response[:500]}")
            
            # STEP 2: Check for FINAL_ANSWER first (highest priority)
            if "FINAL_ANSWER:" in response or "FINAL_ANSWER" in response:
                final_answer = response.split("FINAL_ANSWER:")[-1].strip()
                if verbose:
                    print(f"\n✓ FINAL_ANSWER detected")
                return final_answer
            
            # STEP 3: PARSE ACTION
            thought, action, input_str = self.llm_client.parse_action(response)
            
            if verbose:
                print(f"\nParsed:")
                print(f"  THOUGHT: {thought[:100] if thought else 'None'}")
                print(f"  ACTION: {action}")
                print(f"  INPUT: {input_str}")
            
            self.trace.append({
                "iteration": iteration,
                "thought": thought,
                "action": action,
                "input": input_str,
                "raw_response": response[:300]
            })
            
            # STEP 4: Check if we have an action
            if not action:
                # If no action found, ask LLM to try again with specific format
                if verbose:
                    print(f"\n⚠ No action found, asking LLM to reformat...")
                
                context = f"""Your previous response didn't include a clear action.

Please respond in this exact format:

THOUGHT: [your reasoning]
ACTION: [one of these tool names: {', '.join(self.tools.keys())}]
INPUT: {{"param": "value"}}

Or if you have a final answer:

FINAL_ANSWER: [your complete recommendation]

Previous response was: {response[:200]}"""
                
                continue
            
            # STEP 5: Parse input JSON
            try:
                input_data = json.loads(input_str) if input_str else {}
            except json.JSONDecodeError:
                if verbose:
                    print(f"⚠ Could not parse INPUT as JSON: {input_str}")
                input_data = {}
            
            # STEP 6: EXECUTE TOOL
            result = self.execute_tool(action, input_data)
            
            if verbose:
                print(f"\nTool Result:\n{json.dumps(result, indent=2)[:300]}")
            
            # STEP 7: UPDATE CONTEXT for next iteration
            context = f"""You previously took this action:
ACTION: {action}
INPUT: {json.dumps(input_data)}

The result was:
{json.dumps(result)}

Now continue by either:
1. Taking another ACTION with a tool
2. Providing FINAL_ANSWER with your complete recommendation"""
        
        return "⚠ Max iterations reached without final answer"
    
    def get_trace(self):
        """Return execution trace"""
        return self.trace