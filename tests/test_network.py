import io
import ssl
from unittest.mock import patch
from asterpdf.network import fetch_latest_release, tls_context


def test_bundled_roots_without_machine_ca_paths(monkeypatch):
    monkeypatch.setenv('SSL_CERT_FILE', '/nonexistent/ca.pem')
    monkeypatch.setenv('SSL_CERT_DIR', '/nonexistent')
    context = tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert context.cert_store_stats()['x509_ca'] > 0


def test_update_uses_verified_context():
    with patch('asterpdf.network.urllib.request.urlopen', return_value=io.BytesIO(b'{"tag_name":"v1.2.1"}')) as request:
        assert fetch_latest_release('eternitylzt/AsterPDF', '1.2.1')['tag_name'] == 'v1.2.1'
        assert request.call_args.kwargs['context'].verify_mode == ssl.CERT_REQUIRED
