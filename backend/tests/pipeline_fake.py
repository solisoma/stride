import json
from types import SimpleNamespace


class PipelineClient:
    """Deterministic provider responses; exercises the real pipeline lifecycle."""
    def __init__(self):
        self.chat = SimpleNamespace(completions=self)
        self.calls = []

    def create(self, model, messages, response_format=None, **kwargs):
        name = response_format['json_schema']['name'] if response_format else 'summary'
        self.calls.append(name)
        prompt = messages[-1]['content']
        if name == 'WordBoundaryList':
            result = {'sections': [{'header': 'Learning concept', 'start_word': 0}]}
        elif name == 'ClusteringResponse':
            import re
            indices = [int(i) for i in re.findall(r'^\[(\d+)\]', prompt, re.MULTILINE)]
            size = int(re.search(r'AT MOST (\d+)', prompt).group(1))
            result = {'clusters': [{'cluster_name': f'Concept group {i}', 'child_indices': indices[i:i + size]} for i in range(0, len(indices), size)]}
        elif name == 'RouterResponse':
            import re
            indices = [int(i) for i in re.findall(r'^\[(\d+)\]', prompt, re.MULTILINE)]
            result = {'relevant_children': [{'index': i, 'action': 'DRILL'} for i in indices]}
        else:
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Concept summary.', tool_calls=None))])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(result), tool_calls=None))])

    def parse(self, model, messages, response_format, **kwargs):
        # Exercise the SDK parsed-response contract with deterministic model data.
        schema = {'json_schema': {'name': response_format.__name__}}
        response = self.create(model, messages, response_format=schema, **kwargs)
        message = response.choices[0].message
        message.parsed = response_format.model_validate_json(message.content)
        return response
