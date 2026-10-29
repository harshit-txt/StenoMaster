"""
core/media.py - serves uploaded audio / PDFs to logged-in users.

Why not Django's default static() helper?  Browsers (Safari / iPhone especially) need
"Range" requests to play and seek audio. This view supports them, and it also keeps the
dictation audio private: you must be logged in to download it.

(On a real server you can let nginx serve /media/ instead and delete this view.)
"""
import mimetypes
import os
import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.utils._os import safe_join

CHUNK = 64 * 1024


def _iter_range(path, start, length):
    with open(path, 'rb') as fh:
        fh.seek(start)
        remaining = length
        while remaining > 0:
            data = fh.read(min(CHUNK, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


@login_required
def serve_media(request, path):
    try:
        full = safe_join(settings.MEDIA_ROOT, path)      # blocks "../" tricks
    except SuspiciousFileOperation:
        raise Http404
    if not os.path.isfile(full):
        raise Http404

    size = os.path.getsize(full)
    ctype = mimetypes.guess_type(full)[0] or 'application/octet-stream'
    match = re.match(r'^bytes=(\d*)-(\d*)$', request.headers.get('Range', '').strip())

    if match and (match.group(1) or match.group(2)):
        first, last = match.groups()
        if first == '':                                   # "last N bytes"
            start = max(size - int(last), 0)
            end = size - 1
        else:
            start = int(first)
            end = min(int(last), size - 1) if last else size - 1
        if start >= size or start > end:
            response = HttpResponse(status=416)
            response['Content-Range'] = f'bytes */{size}'
            return response
        length = end - start + 1
        response = StreamingHttpResponse(_iter_range(full, start, length), status=206, content_type=ctype)
        response['Content-Range'] = f'bytes {start}-{end}/{size}'
        response['Content-Length'] = str(length)
    else:
        response = FileResponse(open(full, 'rb'), content_type=ctype)
        response['Content-Length'] = str(size)

    response['Accept-Ranges'] = 'bytes'
    response['Cache-Control'] = 'private, max-age=3600'
    return response
