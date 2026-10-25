from fastapi import APIRouter, Request

from ..web import render

router = APIRouter()


@router.get("/")
def home(request: Request):
    return render(request, "home.html")
