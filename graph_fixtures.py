"""Scripted provider fixture for testing the REAL Deep Agents graph; never a runtime fallback."""
import json
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


def call(name, args=None):
    return {'name': name, 'args': args or {}}


def plan(*requirements):
    return call('plan_request', {'requirements': list(requirements or ['read identity'])})


def finish(evidence='result_1', status='satisfied'):
    return call('finish_request', {'outcomes': [{'requirement': 0, 'status': status, 'evidence_id': evidence}]})


class ScriptModel(BaseChatModel):
    model_name: str = 'thread3-fixture'
    script: list[dict]
    position: int = 0
    advertised: list[list[str]] = []
    observed: list[str] = []

    @property
    def _llm_type(self):
        return 'thread3-scripted-test-provider'

    def _get_ls_params(self, stop=None, **kwargs):
        return {'ls_provider': 'thread3', 'ls_model_name': self.model_name, 'ls_model_type': 'chat'}

    def bind_tools(self, tools, **kwargs):
        self.advertised.append([t.name if hasattr(t, 'name') else t.get('name', t.get('function', {}).get('name')) for t in tools])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.observed.append(json.dumps([{'type': m.type, 'content': m.content} for m in messages]))
        choice = self.script[min(self.position, len(self.script) - 1)]
        self.position += 1
        message = AIMessage(content='', tool_calls=[{'id': 'fixture_' + str(self.position), **choice}])
        return ChatResult(generations=[ChatGeneration(message=message)])
