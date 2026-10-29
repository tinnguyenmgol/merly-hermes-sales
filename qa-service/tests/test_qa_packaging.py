from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_image_context_is_strictly_the_new_qa_service():
    allowed={s[1:] for s in (ROOT/'.dockerignore').read_text().splitlines() if s.startswith('!')}
    assert allowed=={'Dockerfile','requirements.txt','qa_transport.py','qa_core.py','qa_server.py'}
    docker=(ROOT/'Dockerfile').read_text()
    assert 'USER 10001:10001' in docker and 'hermes-config.template' not in docker
    compose=(ROOT/'compose.qa.yaml').read_text()
    assert 'read_only: true' in compose and 'cap_drop: [ALL]' in compose and 'ports:' not in compose
    assert 'docker.sock' not in compose and 'privileged:' not in compose
