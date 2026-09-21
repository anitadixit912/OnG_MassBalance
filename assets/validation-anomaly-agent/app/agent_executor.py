import logging
from a2a.server.agent_execution import AgentExecutor as A2AAgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import InternalError, Part, TaskState, TextPart, UnsupportedOperationError
from a2a.utils import new_agent_text_message, new_task
from a2a.utils.errors import ServerError
from agent import SampleAgent
from load_skill_resources import get_load_skill_resource_tool
from mcp_providers.agw import get_mcp_tools
from prompt_injection_detector import wrap_tool

logger = logging.getLogger(__name__)

class AgentExecutor(A2AAgentExecutor):
    def __init__(self):
        self.agent = SampleAgent()
        self.skill_tools = get_load_skill_resource_tool()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        query = context.get_user_input()
        task = context.current_task
        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        tools = []
        try:
            tools = await get_mcp_tools()
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")
        tools = [wrap_tool(t) for t in [*tools, *self.skill_tools]]
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        try:
            async for item in self.agent.stream(query, task.context_id, tools=tools):
                if item["require_user_input"]:
                    await updater.update_status(TaskState.input_required, new_agent_text_message(item["content"], task.context_id, task.id), final=True)
                    break
                elif item["is_task_complete"]:
                    await updater.add_artifact([Part(root=TextPart(text=item["content"]))], name="validation_result")
                    await updater.complete()
                    break
                else:
                    await updater.update_status(TaskState.working, new_agent_text_message(item["content"], task.context_id, task.id))
        except Exception as e:
            logger.exception("Agent execution error")
            raise ServerError(error=InternalError()) from e

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())
