import json
import pytest
from app.adapters import AdapterError, MockAdapter, OpenAICompatibleAdapter, AnthropicAdapter, normalize

E=[{'evidence_id':'A','text':'Verified evidence.'}]

def test_output_validation():
    valid=normalize(json.dumps({'predicted_label':'SUPPORTED','explanation':'Verified','cited_evidence_ids':['A']}),E)
    assert valid.predicted_label=='SUPPORTED'
    for bad in ('not json',json.dumps({'predicted_label':'CERTAIN','explanation':'','cited_evidence_ids':[]}),json.dumps({'predicted_label':'SUPPORTED','explanation':'','cited_evidence_ids':['unknown']})):
        with pytest.raises(AdapterError):normalize(bad,E)

def test_mock_repeatable_and_gold_independent():
    a=MockAdapter()
    assert a.predict('A claim',E,42)==a.predict('A claim',E,42)

def test_missing_provider_credentials(monkeypatch):
    monkeypatch.delenv('MODELAUDIT_OPENAI_API_KEY',raising=False)
    monkeypatch.delenv('MODELAUDIT_ANTHROPIC_API_KEY',raising=False)
    with pytest.raises(AdapterError):OpenAICompatibleAdapter('test-model')
    with pytest.raises(AdapterError):AnthropicAdapter('test-model')

def test_openai_adapter_normalizes_response(monkeypatch):
    import httpx
    original=httpx.Client
    monkeypatch.setenv('MODELAUDIT_OPENAI_API_KEY','test-not-real')
    monkeypatch.setenv('MODELAUDIT_OPENAI_BASE_URL','https://example.test/v1')
    handler=lambda req:httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'predicted_label':'REFUTED','explanation':'Evidence contradicts claim','cited_evidence_ids':['A']})}}],'usage':{'prompt_tokens':20,'completion_tokens':13}})
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    result=OpenAICompatibleAdapter('demo').predict('claim',E)
    assert result.predicted_label=='REFUTED'
    assert result.input_tokens==20 and result.output_tokens==13

def test_anthropic_adapter_normalizes_response(monkeypatch):
    import httpx
    original=httpx.Client
    monkeypatch.setenv('MODELAUDIT_ANTHROPIC_API_KEY','test-not-real')
    handler=lambda req:httpx.Response(200,json={'content':[{'type':'text','text':json.dumps({'predicted_label':'SUPPORTED','explanation':'Shown','cited_evidence_ids':['A']})}],'usage':{'input_tokens':11,'output_tokens':7}})
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    result=AnthropicAdapter('demo').predict('claim',E)
    assert result.predicted_label=='SUPPORTED' and result.output_tokens==7
