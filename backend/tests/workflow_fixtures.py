"""Controlled SIMULATED diagnostics and scripted selectors; never production providers."""
import json
from datetime import datetime, timezone

from tests.agent_fixtures import TestDiagnostics, tool


class WorkflowDiagnostics(TestDiagnostics):
    def __init__(self, scenario='healthy'):
        super().__init__()
        self.scenario = scenario

    async def execute(self, name, arguments, target='demo'):
        result = await super().execute(name, arguments, target)
        if name == 'service_health':
            result['data']['services'].append({'service': 'backend', 'status': 'healthy'})
            for item in result['data']['services']:
                if self.scenario == 'database_failure' and item['service'] == 'database':
                    item['status'] = 'unavailable'
                if self.scenario in {'stopped', 'unhealthy'} and item['service'] == 'demo':
                    item['status'] = 'unavailable'
        if name == 'inspect_container':
            result['data']['id_prefix'] = 'a'*12
            if self.scenario == 'stopped':
                result['data'].update(running=False, status='exited', health_status='not_configured')
            if self.scenario == 'unhealthy':
                result['data']['health_status'] = 'unhealthy'
        if name == 'container_stats' and self.scenario == 'high_memory':
            result['data'].update(memory_usage_bytes=95*1048576, memory_limit_bytes=100*1048576)
        result['measurement'] = 'simulated'
        result['observed_at'] = datetime.now(timezone.utc).isoformat()
        return result


class WorkflowProvider:
    def __init__(self):
        self.calls = []
        self.status_calls = 0

    async def status(self):
        self.status_calls += 1
        return {'ready': True, 'state': 'ready', 'detail': 'Scripted test selector', 'model': 'test-model'}

    async def chat(self, messages, **kwargs):
        self.calls.append(kwargs)
        if 'tools' in kwargs:
            return {'content': '', 'tool_calls': [tool(item['function']['name'])['tool_calls'][0] for item in kwargs['tools']]}
        content = json.loads(messages[-1]['content'])
        if 'ids' in kwargs['schema']['properties']:
            return {'content': json.dumps({'ids': [group[0] for group in content['required_groups']]})}
        catalog = content['catalog']
        return {'content': json.dumps({'observations': catalog['required_observations'] or [catalog['observations'][0]['id']],
            'hypotheses': [], 'recommendations': [catalog['recommendations'][0]['id']]})}
