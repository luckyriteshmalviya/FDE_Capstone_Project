"""A11 fault injection for the offline classifier/retriever and unattended harness.

No network provider is used. RateLimitError below is a synthetic dependency error,
not a claim that the application has real provider-side rate limiting.
"""
import json
import pytest
from src.pipeline import Pipeline
from evaluation import harness

TICKET = {'ticket_id': 'FAULT-1', 'channel': 'email', 'subject': 'API help', 'body': 'How do I use the API?'}


@pytest.fixture(scope='module')
def pipeline():
    return Pipeline()


@pytest.mark.parametrize('error', [TimeoutError('simulated timeout'), ConnectionError('simulated outage')])
def test_classifier_dependency_failure_safely_escalates(pipeline, monkeypatch, error):
    def fail(_):
        raise error
    monkeypatch.setattr(pipeline, 'classify', fail)
    result = pipeline.process(TICKET)
    assert result['status'] == 'escalated'
    assert result['route'] == 'escalate'
    assert result['answer'] is None
    assert result['validation']['performed'] is False
    assert type(error).__name__ in result['reason']


class SimulatedRateLimitError(Exception):
    """Simulates an upstream rate-limit exception; no upstream service exists."""


def test_retrieval_rate_limit_safely_escalates(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline, 'classify', lambda _: {'intent':'api_usage_question', 'urgency':'medium', 'confidence':0.99, 'alternatives':[]})
    def fail(_):
        raise SimulatedRateLimitError('synthetic 429')
    monkeypatch.setattr(pipeline, 'retrieve', fail)
    result = pipeline.process(TICKET)
    assert result['status'] == 'escalated'
    assert result['answer'] is None
    assert 'SimulatedRateLimitError' in result['reason']
    assert result['sources'] == []


def test_answer_validation_outage_safely_escalates(pipeline, monkeypatch):
    monkeypatch.setattr(pipeline, 'classify', lambda _: {'intent':'api_usage_question', 'urgency':'medium', 'confidence':0.99, 'alternatives':[]})
    monkeypatch.setattr(pipeline, 'retrieve', lambda _: [{'passage_id':'DOC-TEST#p0', 'doc_id':'DOC-TEST', 'title':'Test', 'text':'You can find the API reference in the documentation portal.'}])
    def fail(*_):
        raise ConnectionError('validator unavailable')
    monkeypatch.setattr(pipeline, 'validate', fail)
    result = pipeline.process(TICKET)
    assert result['status'] == 'escalated'
    assert result['answer'] is None
    assert 'ConnectionError' in result['reason']


def test_unattended_batch_continues_after_uncaught_ticket_error(tmp_path, monkeypatch):
    input_path = tmp_path / 'tickets.json'
    tickets = [{**TICKET, 'ticket_id': f'FAULT-{i}'} for i in range(3)]
    input_path.write_text(json.dumps(tickets), encoding='utf-8')
    original_process = Pipeline.process
    def intermittent(self, ticket):
        if ticket['ticket_id'] == 'FAULT-1':
            raise RuntimeError('injected unexpected crash')
        return original_process(self, ticket)
    monkeypatch.setattr(Pipeline, 'process', intermittent)
    output = tmp_path / 'results'
    metrics = harness.evaluate(input_path, output)
    results = [json.loads(line) for line in (output / 'decisions.jsonl').read_text(encoding='utf-8').splitlines()]
    assert metrics['complete_run'] is True
    assert metrics['tickets_processed'] == metrics['decisions_logged'] == 3
    assert len(results) == 3
    assert results[1]['route'] == 'escalate' and results[1]['answer'] is None
    assert 'Uncaught failure safely escalated' in results[1]['reason']
    assert results[2]['ticket_id'] == 'FAULT-2'


def test_malformed_ticket_does_not_crash(pipeline):
    result = pipeline.process(None)
    assert result['route'] == 'escalate'
    assert result['answer'] is None
