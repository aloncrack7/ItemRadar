# orchestrator_agent/agent.py

import json
from google.adk.agents import BaseAgent, SequentialAgent, LoopAgent
from google.adk.events import Event, EventActions
from google.adk.tools import AgentTool
from google.genai import types

from matcher_agent_dir.agent   import matcher_agent
from reductor_agent_dir.agent  import reductor_agent
from filter_agent_dir.agent    import filter_agent


# Wrap each LlmAgent in an AgentTool for explicit invocation
matcher_tool  = AgentTool(agent=matcher_agent)
reductor_tool = AgentTool(agent=reductor_agent)
filter_tool   = AgentTool(agent=filter_agent)


class CheckTermination(BaseAgent):
    """
    Custom agent that inspects state['match_results'] and
    signals LoopAgent to stop if <= 1 match remains.
    """
    async def _run_async_impl(self, ctx):
        matches = ctx.session.state.get("match_results", [])
        done = len(matches) <= 1
        # escalate=True stops the loop when done==True
        yield Event(author=self.name, actions=EventActions(escalate=done))


# 1) First, run matcher_agent to populate state['match_results']
# 2) Then, enter LoopAgent of [reductor_agent, filter_agent, CheckTermination]
refinement_loop = LoopAgent(
    name="refinement_loop",
    sub_agents=[
        # Clarifying question
        reductor_agent,
        # Apply user answer to filter
        filter_agent,
        # Check if we should stop looping
        CheckTermination(name="termination_checker")
    ],
    max_iterations=10  # safety cap
)

# Entire pipeline: matcher → (reductor→filter)*
lost_and_found_pipeline = SequentialAgent(
    name="lost_found_pipeline",
    sub_agents=[
        matcher_agent,       # initial semantic matching
        refinement_loop      # iterative refinement
    ]
)

# Export for ADK runtime
primary_agent = lost_and_found_pipeline
__all__ = ["primary_agent"]
