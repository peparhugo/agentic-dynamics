import xml.etree.ElementTree as ET

import pytest
from aiohttp.test_utils import TestClient, TestServer

from notification_server.registry import ClientRegistry
from notification_server.soap import SOAP_NS, TNS, create_soap_app


@pytest.fixture
async def soap_client():
    registry = ClientRegistry()
    app = create_soap_app(registry)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client, registry
    await client.close()


async def test_get_health_returns_soap_envelope_with_zero_clients(soap_client):
    client, _registry = soap_client
    resp = await client.get("/health")
    assert resp.status == 200
    assert resp.content_type == "text/xml"
    body = await resp.text()
    root = ET.fromstring(body)
    assert root.tag == f"{{{SOAP_NS}}}Envelope"
    count_el = root.find(f".//{{{TNS}}}connectedClients")
    assert count_el.text == "0"


async def test_get_health_reflects_connected_count(soap_client):
    client, registry = soap_client
    registry.add("a", object())
    registry.add("b", object())
    resp = await client.get("/health")
    body = await resp.text()
    root = ET.fromstring(body)
    assert root.find(f".//{{{TNS}}}connectedClients").text == "2"


async def test_get_health_wsdl(soap_client):
    client, _registry = soap_client
    resp = await client.get("/health", params={"wsdl": ""})
    assert resp.status == 200
    body = await resp.text()
    assert "<definitions" in body
    assert "GetHealth" in body


async def test_post_health_returns_soap_envelope(soap_client):
    client, registry = soap_client
    registry.add("a", object())
    envelope = (
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soap:Body><GetHealthRequest xmlns="urn:notification-server"/></soap:Body>'
        "</soap:Envelope>"
    )
    resp = await client.post("/health", data=envelope, headers={"Content-Type": "text/xml"})
    assert resp.status == 200
    body = await resp.text()
    root = ET.fromstring(body)
    assert root.find(f".//{{{TNS}}}connectedClients").text == "1"


async def test_post_health_malformed_xml_returns_soap_fault(soap_client):
    client, _registry = soap_client
    resp = await client.post("/health", data="<not-xml", headers={"Content-Type": "text/xml"})
    assert resp.status == 400
    body = await resp.text()
    assert "Fault" in body
    assert "faultstring" in body


async def test_post_health_empty_body_still_works(soap_client):
    client, _registry = soap_client
    resp = await client.post("/health", data="", headers={"Content-Type": "text/xml"})
    assert resp.status == 200
