from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.models import LibraryBook
from matching.catalog import load_catalog
from matching.matcher import AUTO, match_spine
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


def _library_payload(book):
    return {
        'id': book.id,
        'catalog_id': book.catalog_id,
        'title': book.title,
        'author': book.author,
        'decision': book.decision,
    }


def _add_catalog_book(entry, decision):
    book, _ = LibraryBook.objects.get_or_create(
        catalog_id=entry.id,
        defaults={
            'title': entry.title,
            'author': entry.author,
            'decision': decision,
        },
    )
    return book


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
    automatic_books = [
        _add_catalog_book(result.best.entry, 'automatic')
        for result in results
        if result.status == AUTO and result.best is not None
    ]

    return Response(
        {
            'provider': 'fake',
            'message': 'Demo analysis uses fixed spine reads while the model integration is pending.',
            'results': [_result_payload(result) for result in results],
            'automatic_books': [_library_payload(book) for book in automatic_books],
        }
    )


@api_view(['GET', 'POST'])
def library(request):
    """List confirmed books or persist one review decision."""
    if request.method == 'GET':
        return Response({'books': [_library_payload(book) for book in LibraryBook.objects.all()]})

    catalog_id = request.data.get('catalog_id')
    title = (request.data.get('title') or '').strip()
    author = (request.data.get('author') or '').strip()

    if catalog_id:
        entry = next((item for item in load_catalog() if item.id == str(catalog_id)), None)
        if entry is None:
            return Response({'detail': 'The selected catalog entry does not exist.'}, status=400)

        book = _add_catalog_book(entry, request.data.get('decision') or 'confirmed')
        return Response(_library_payload(book), status=201)

    if not title:
        return Response({'detail': 'Enter a title or select a catalog suggestion.'}, status=400)

    book = LibraryBook.objects.create(title=title, author=author, decision='corrected')
    return Response(_library_payload(book), status=201)
