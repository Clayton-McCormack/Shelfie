from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def health(request):
    """Liveness probe.

    Exists so the phone can prove it can reach this server over the LAN before
    any of the vision pipeline is involved. When an upload misbehaves later,
    this separates "the network is wrong" from "the pipeline is wrong".
    """
    return Response({'status': 'ok'})
