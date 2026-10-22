#!/bin/bash
# -i — show us the HTTP status and headers as part of the manual acceptance.
# --data-binary — send the XML essentially as-is.
# SOAPAction — exactly what the frozen WSDL specifies for GetCrewMember.
# Endpoint — exactly what the deployment WSDL specifies.

curl -i \
  -X POST \
  -H "Content-Type: text/xml; charset=utf-8" \
  -H 'SOAPAction: "urn:graphql-federation-lab:crew-personnel:v1:GetCrewMember"' \
  --data-binary @get-picard.xml \
  http://127.0.0.1:8081/soap/crew-personnel