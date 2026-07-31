from django.http import HttpResponse

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def webhook(request):
    from loguru import logger
    logger.info(f"webhook received: body={request.body.decode('utf-8')}")
    return HttpResponse(status=200)