from rest_framework.decorators import api_view
from rest_framework.response import Response

from matching.matcher import match_spine
from vision.providers import FakeProvider


@api_view(['GET'])
def health(request):
    """Liveness probe.

    Confirms LAN reachability between handset and API independently of the
    vision pipeline. When an upload later fails, this endpoint distinguishes a
    networking fault from a pipeline fault.
    """
    return Response({'status': 'ok'})


def _candidate_payload(candidate):
    entry = candidate.entry
    return {
        'id': entry.id,
        'title': entry.title,
        'author': entry.author,
        'year': entry.year,
        'edition': entry.edition,
        'score': round(candidate.score, 3),
    }


def _result_payload(result):
    return {
        'read_title': result.read_title,
        'read_author': result.read_author,
        'status': result.status,
        'confidence': result.confidence,
        'reasons': list(result.reasons),
        'candidates': [_candidate_payload(candidate) for candidate in result.candidates],
    }


@api_view(['POST'])
def analyse(request):
    """Accept one shelf photo and return catalog matches for its spine reads.

    The initial implementation uses FakeProvider. The HTTP contract stays the
    same when local detection and a hosted VLM replace the fixed reads, which
    lets the mobile client be tested now without an API key or model latency.
    """
    image = request.FILES.get('image')
    if image is None:
        return Response({'detail': 'Attach a photo in the image field.'}, status=400)

    if not image.content_type.startswith('image/'):
        return Response({'detail': 'The uploaded file must be an image.'}, status=400)

    reads = FakeProvider().read_spines(image)
    results = [match_spine(read.title, read.author) for read in reads]

    return Response(
        {
            'provider': 'fake',
            'message': 'Demo analysis uses fixed spine reads while the model integration is pending.',
            'results': [_result_payload(result) for result in results],
        }
    )
