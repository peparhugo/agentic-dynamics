"""SOAP 1.1 health API, served over aiohttp.

The brief asked for a REST `GET /health` endpoint, then added a hard
constraint that the API must be SOAP, not REST. Both are honored as far as
they can be reconciled: `GET /health` keeps the path/verb from the brief, but
its body is a SOAP envelope rather than bare REST/JSON. A canonical
`POST /health` SOAP operation and a WSDL document are also exposed for
clients that expect a proper SOAP RPC call instead of a GET.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from aiohttp import web

from .registry import ClientRegistry
from .store import MessageStore

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TNS = "urn:notification-server"

WSDL = f"""<?xml version="1.0" encoding="UTF-8"?>
<definitions name="NotificationServer"
             targetNamespace="{TNS}"
             xmlns="http://schemas.xmlsoap.org/wsdl/"
             xmlns:tns="{TNS}"
             xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
             xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <message name="GetHealthRequest"/>
  <message name="GetHealthResponse">
    <part name="status" type="xsd:string"/>
    <part name="connectedClients" type="xsd:int"/>
  </message>
  <portType name="NotificationServerPortType">
    <operation name="GetHealth">
      <input message="tns:GetHealthRequest"/>
      <output message="tns:GetHealthResponse"/>
    </operation>
  </portType>
  <binding name="NotificationServerBinding" type="tns:NotificationServerPortType">
    <soap:binding style="rpc" transport="http://schemas.xmlsoap.org/soap/http"/>
    <operation name="GetHealth">
      <soap:operation soapAction="urn:notification-server#GetHealth"/>
      <input><soap:body use="literal" namespace="{TNS}"/></input>
      <output><soap:body use="literal" namespace="{TNS}"/></output>
    </operation>
  </binding>
  <service name="NotificationServerService">
    <port name="NotificationServerPort" binding="tns:NotificationServerBinding">
      <soap:address location="http://localhost:8080/health"/>
    </port>
  </service>
</definitions>"""


def build_health_envelope(connected_clients: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<soap:Envelope xmlns:soap="{SOAP_NS}"><soap:Body>'
        f'<GetHealthResponse xmlns="{TNS}">'
        "<status>ok</status>"
        f"<connectedClients>{connected_clients}</connectedClients>"
        "</GetHealthResponse></soap:Body></soap:Envelope>"
    )


def build_fault(message: str, code: str = "soap:Client") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<soap:Envelope xmlns:soap="{SOAP_NS}"><soap:Body>'
        f"<soap:Fault><faultcode>{code}</faultcode>"
        f"<faultstring>{message}</faultstring></soap:Fault>"
        "</soap:Body></soap:Envelope>"
    )


def create_soap_app(registry: ClientRegistry, store: MessageStore | None = None) -> web.Application:
    async def list_messages(request: web.Request) -> web.Response:
        try:
            limit = int(request.query.get("limit", 50))
            offset = int(request.query.get("offset", 0))
        except ValueError:
            return web.json_response(
                {"error": "limit and offset must be integers"}, status=400
            )
        if limit < 0 or offset < 0:
            return web.json_response(
                {"error": "limit and offset must be non-negative"}, status=400
            )
        if store is None:
            return web.json_response({"messages": []})
        messages = await store.alist_messages(limit=limit, offset=offset)
        return web.json_response({"messages": messages})

    async def list_channels(request: web.Request) -> web.Response:
        channels = [
            {"name": name, "subscribers": count}
            for name, count in sorted(registry.channels().items())
        ]
        return web.json_response({"channels": channels})

    async def get_channel_subscribers(request: web.Request) -> web.Response:
        name = request.match_info["name"]
        return web.json_response(
            {"channel": name, "subscribers": registry.channel_subscribers(name)}
        )

    async def wsdl_handler(request: web.Request) -> web.Response:
        return web.Response(text=WSDL, content_type="text/xml")

    async def get_health(request: web.Request) -> web.Response:
        if "wsdl" in request.query:
            return await wsdl_handler(request)
        return web.Response(
            text=build_health_envelope(registry.count()), content_type="text/xml"
        )

    async def post_health(request: web.Request) -> web.Response:
        body = await request.text()
        if body.strip():
            try:
                ET.fromstring(body)
            except ET.ParseError as exc:
                return web.Response(
                    text=build_fault(f"Malformed SOAP envelope: {exc}"),
                    content_type="text/xml",
                    status=400,
                )
        return web.Response(
            text=build_health_envelope(registry.count()), content_type="text/xml"
        )

    app = web.Application()
    app.router.add_get("/health", get_health)
    app.router.add_post("/health", post_health)
    app.router.add_get("/channels", list_channels)
    app.router.add_get("/channels/{name}/subscribers", get_channel_subscribers)
    app.router.add_get("/messages", list_messages)
    return app
