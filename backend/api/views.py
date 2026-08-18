from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def health(request):
    """Liveness probe.

    Confirms LAN reachability between handset and API independently of the
    vision pipeline. When an upload later fails, this endpoint distinguishes a
    networking fault from a pipeline fault.
    """
    return Response({'status': 'ok'})
